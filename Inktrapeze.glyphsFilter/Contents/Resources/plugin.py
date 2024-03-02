# encoding: utf-8

###########################################################################################################
#
#
#	Filter with dialog Plugin
#
#	Read the docs:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Filter%20with%20Dialog
#
#	For help on the use of Interface Builder:
#	https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates
#
#
###########################################################################################################

# TODO: preview
# TODO: curved or straight inktrap
# TODO: fix crash when prevNode or nextNode is first node
# TODO: Calculate area inside inktrap, base length of trap on that area (using distance between intersections,
#  and the fact that the trap is symmetrical)
# height of triangle: desired area times 2, divided by distance between intersections
# threshold: factor to multiple area of circle by to get minimum area of trap
# if area of triangle (intersection b, intersection c, selected node) is less than circle area times threshold, 
# make inktrap 


from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import Glyphs, GSNode, OFFCURVE, distance, DRAWFOREGROUND
from GlyphsApp.plugins import FilterWithDialog
from math import sqrt, dist, sin, acos, atan2, degrees, radians, cos, pi
from Foundation import NSPoint, NSColor


class Inktrapeze(FilterWithDialog):

	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()

	# Text field in dialog
	apertureTextField = objc.IBOutlet()
	straightRadio = objc.IBOutlet()
	curvedRadio = objc.IBOutlet()
	flatTopRadio = objc.IBOutlet()

	@objc.python_method
	def settings(self):
		self.menuName = Glyphs.localize({
			"en": "Inktrapeze",
		})

		# Word on Run Button (default: Apply)
		self.actionButtonLabel = Glyphs.localize({
			"en": "Apply",
			"de": "Anwenden",
			"fr": "Appliquer",
			"es": "Aplicar",
			"pt": "Aplique",
			"jp": "申し込む",
			"ko": "대다",
			"zh": "应用",
		})

		# Load dialog from .nib (without .extension)
		self.loadNib("IBdialog", __file__)

	# On dialog show
	@objc.python_method
	def start(self):
		Glyphs.registerDefaults({
			"com.eweracs.inktrapeze.aperture": 20,
			"com.eweracs.inktrapeze.flatTopSize": 10,
			"com.eweracs.inktrapeze.threshold": 1,
			"com.eweracs.inktrapeze.depth": 1,
			"com.eweracs.inktrapeze.straight": True,
		})
		# Set focus to text field
		self.apertureTextField.becomeFirstResponder()
		Glyphs.addCallback(self.draw_calculations, DRAWFOREGROUND)

	@objc.IBAction
	def update_(self, sender):
		self.update()

	@objc.IBAction
	def setStraight_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = bool(sender.state())
		self.curvedRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = False
		self.flatTopRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = False
		self.update()

	@objc.IBAction
	def setCurved_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = bool(sender.state())
		self.straightRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = False
		self.flatTopRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = False
		self.update()

	@objc.IBAction
	def setFlatTop_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = bool(sender.state())
		self.straightRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = False
		self.curvedRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = False
		self.update()

	# Actual filter
	@objc.python_method
	def filter(self, layer, inEditView, customParameters):
		aperture = float(Glyphs.defaults["com.eweracs.inktrapeze.aperture"])
		threshold = 3 - float(Glyphs.defaults["com.eweracs.inktrapeze.threshold"])
		depth = float(Glyphs.defaults["com.eweracs.inktrapeze.depth"])
		straight = Glyphs.boolDefaults["com.eweracs.inktrapeze.straight"]
		curved = Glyphs.boolDefaults["com.eweracs.inktrapeze.curved"]
		flat_top = Glyphs.boolDefaults["com.eweracs.inktrapeze.flatTop"]
		flat_top_size = Glyphs.intDefaults["com.eweracs.inktrapeze.flatTopSize"]

		if inEditView:
			for node in list(layer.selection):
				if not isinstance(node, GSNode):
					continue
				self.create_inktrap_for_node(node, aperture, threshold, depth, straight, curved, flat_top, flat_top_size)
		else:
			pass # process all nodes with a sharp angle
		# for path in layer.paths:
		# 	for node in list(path.nodes):
		# 		if node.selected:
		# 			self.create_inktrap_for_node(node, aperture, threshold, depth, straight, curved, flat_top, flat_top_size)

	@objc.python_method
	def calculate_inktrap_position(self, node, prev_node, next_node, aperture, threshold, depth):
		# calculate the distance between the other two nodes
		dist_prev_node_to_next_node = distance(prev_node.position, next_node.position)
		# calculate the distance between the prev node and the selected node
		dist_current_node_to_prev_node = distance(node.position, prev_node.position)
		# calculate the distance between the next node and the selected node
		dist_current_node_next_node = distance(node.position, next_node.position)

		if prev_node is None or next_node is None:
			print("!! a Node is not connected to other nodes.")
			return None, None, None
		if prev_node.type == OFFCURVE or next_node.type == OFFCURVE:
			print("!! b Node is an offcurve node.")
			return None, None, None

		# calculate the angle at the selected node
		angle_at_current_node = self.calculate_angle_at_node(node, prev_node, next_node)

		# Construct a circle with the diameter of the aperture and see how far it can be pushed into the triangle at the
		# selected node.
		# Then calculate the distance from the intersection of the circle with the right line to the intersection with
		# the left line.

		# To achieve this, construct a right triangle with these points: center of circle, intersection with right line,
		# the selected node. The angle at the intersection with both lines is 90 degrees. The angle at the selected
		# node is half the original angle at the selected node and the angle at the circle center is 90 minus the angle
		# at the selected node. The distance from the center of the circle to the intersection with any of the two lines
		# is the radius of the circle.

		# The distance from the selected node to either intersection point can be calculated using a triangle with the
		# given parameters: the selected node, half the angle at the selected node, the radius of the circle.

		distance_from_node_to_intersection = self.cathetus_for_cathetus_angle(aperture / 2, angle_at_current_node / 2)

		# Then construct a triangle with the given parameters: the selected node, the angle at the selected node, the
		# distance from the selected node to both intersection points with the circle. Calculate the area of this
		# triangle.

		# Calculate the angle of the line between the selected node and the previous node
		angle_prev_node = self.calculate_angle(node, prev_node)

		# Calculate the angle of the line between the selected node and the next node
		angle_next_node = self.calculate_angle(node, next_node)

		# First, calculate the node positions of the intersections with the circle
		intersection_previous_node = self.position_for_angle_distance(
			node, angle_prev_node, distance_from_node_to_intersection
		)
		intersection_next_node = self.position_for_angle_distance(
			node, angle_next_node, distance_from_node_to_intersection
		)

		# calculate the distance between the intersections
		dist_between_intersections = distance(intersection_previous_node, intersection_next_node)

		# find area of triangle of intersection points and selected node
		# = self.triangle_area(
		#	dist_between_intersections,
		#	dist_current_node_to_prev_node,
		#	dist_current_node_next_node
		#)

		# calculate distance of the center of the circle to the selected node
		distance_circle_center_to_node = self.hypotenuse_for_cathetus_cathetus(
			aperture / 2,
			distance_from_node_to_intersection
		)

		# calculate the position of the center of the circle. Depending on the path direction, the order of the angles
		# used to calculate the position needs to be adjusted.
		angle = angle_prev_node if angle_prev_node < angle_next_node else angle_next_node
		center_of_circle = self.position_for_angle_distance(
			node,
			angle + angle_at_current_node / 2,
			distance_circle_center_to_node
		)

		# check whether the distance from the circle center to the selected node divided by the aperture is smaller than
		# the threshold, if so, skip.
		# For example, if the threshold is 1, the selected node must be at least one aperture away from the center of
		# the circle. The higher the threshold, the further away the selected node must be from the center of the circle
		# before an inktrap is created.

		if distance_circle_center_to_node / aperture < threshold:
			print("!! c", distance_circle_center_to_node, aperture, threshold)
			return None, None, None
		return center_of_circle, intersection_previous_node, intersection_next_node

	@objc.python_method
	def calculate_angle(self, node1, node2):
		delta_y = node2.position.y - node1.position.y
		delta_x = node2.position.x - node1.position.x
		angle_rad = atan2(delta_y, delta_x)
		angle_deg = degrees(angle_rad)
		return angle_deg

	@objc.python_method
	def calculate_angle_at_node(self, node, prev_node, next_node):
		# calculate the distance between the other two nodes
		dist_prev_node_to_next_node = distance(prev_node.position, next_node.position)
		# calculate the distance between the prev node and the selected node
		dist_current_node_to_prev_node = distance(node.position, prev_node.position)
		# calculate the distance between the next node and the selected node
		dist_current_node_next_node = distance(node.position, next_node.position)
		# calculate the angle at the selected node
		angle_at_current_node = degrees(
			acos(
				(dist_current_node_to_prev_node ** 2 + dist_current_node_next_node ** 2 - dist_prev_node_to_next_node ** 2)
				/ (2 * dist_current_node_to_prev_node * dist_current_node_next_node)
			)
		)

		return angle_at_current_node

	@objc.python_method
	def position_for_angle_distance(self, node, angle, distance):
		return NSPoint(node.position.x + distance * cos(radians(angle)), node.position.y + distance * sin(radians(angle)))

	@objc.python_method
	def cathetus_for_cathetus_angle(self, cathetus, angle):
		return cathetus / sin(radians(angle))

	@objc.python_method
	def hypotenuse_for_cathetus_cathetus(self, cathetus1, cathetus2):
		return sqrt(cathetus1 ** 2 + cathetus2 ** 2)

	@objc.python_method
	def triangle_area(self, a, b, c):
		s = (a + b + c) / 2
		return sqrt(s * (s - a) * (s - b) * (s - c))

	@objc.python_method
	def circle_area(self, radius):
		return pi * radius ** 2

	@objc.python_method
	def calculate_intersection_path_time(self, node, other_node, intersection):
		intersection_path_time = (distance(node.position, intersection) / distance(node.position, other_node.position))
		return intersection_path_time

	@objc.python_method
	def center_between_points(self, point1, point2):
		return NSPoint((point1.x + point2.x) / 2, (point1.y + point2.y) / 2)

	@objc.python_method
	def create_inktrap_for_node(self, node, aperture, threshold, depth, straight=True, curved=False, flat_top=False,
								flat_top_size=5):
		# there are three nodes that form a triangle. A center node ("node") and one left and one right node ("left_node" and
		# "right_node")

		path = node.parent

		prev_node = node.prevNode
		next_node = node.nextNode

		center_of_circle, intersection_previous_node, intersection_next_node = self.calculate_inktrap_position(
			node, prev_node, next_node, aperture, threshold, depth
		)

		if not center_of_circle or not intersection_previous_node or not intersection_next_node:
			return

		center_between_intersections = self.center_between_points(intersection_previous_node, intersection_next_node)

		# calculate the position of a new node which is on an extension of the line from the center of the
		# intersections to the selected node. Use the depth as a factor by which to extend the line negatively.
		new_node_position = NSPoint(
			node.position.x + (node.position.x - center_between_intersections.x) * depth,
			node.position.y + (node.position.y - center_between_intersections.y) * depth
		)

		node.position = new_node_position

		# insert nodes at the intersections (the beginning of the inktrap)
		path.nodes.insert(node.index, GSNode(intersection_previous_node))
		path.nodes.insert(node.index + 1, GSNode(intersection_next_node))

		path.nodes.insert(node.index, GSNode(center_of_circle))

		return

		if curved:
			# find the point which is on the extension of the line from prev_node to intersection_b. The extra
			# distance from the intersection to the new point is relative to depth and the distance of the selected
			# node to the intersection
			distance_factor = dist([node.position.x, node.position.y], [intersection_b.x, intersection_b.y]) \
			                  / dist([intersection_b.x, intersection_b.y], [prev_node.position.x, prev_node.position.y])

			offcurve_1 = NSPoint(intersection_b.x + (intersection_b.x - prev_node.position.x) * distance_factor / 3,
			                     intersection_b.y + (intersection_b.y - prev_node.position.y) * distance_factor / 3)

			# find the point which is on the extension of the line from intersection_b to offcurve_1
			reference_1 = NSPoint(offcurve_1.x + (offcurve_1.x - intersection_b.x),
			                      offcurve_1.y + (offcurve_1.y - intersection_b.y))

			# find the point which is one third of the way from the selected node to intersection_b
			reference_2 = NSPoint(node.position.x - (node.position.x - intersection_b.x) / 3,
			                      node.position.y - (node.position.y - intersection_b.y) / 3)

			offcurve_2 = NSPoint((reference_1.x + reference_2.x) / 2, (reference_1.y + reference_2.y) / 2)

			path.nodes.insert(node.index, GSNode(offcurve_1, OFFCURVE))
			path.nodes[node.index - 2].smooth = True
			path.nodes.insert(node.index, GSNode(offcurve_2, OFFCURVE))
			node.type = CURVE

			# find the point which is on the extension of the line from next_node to intersection_c. The extra
			# distance from the intersection to the new point is relative to depth and the distance of the selected
			# node to the intersection
			distance_factor = dist([node.position.x, node.position.y], [intersection_c.x, intersection_c.y]) / dist([
				intersection_c.x, intersection_c.y], [next_node.position.x, next_node.position.y])

			offcurve_3 = NSPoint(intersection_c.x + (intersection_c.x - next_node.position.x) * distance_factor / 3,
			                     intersection_c.y + (intersection_c.y - next_node.position.y) * distance_factor / 3)
			reference_3 = NSPoint(offcurve_3.x + (offcurve_3.x - intersection_c.x),
			                     offcurve_3.y + (offcurve_3.y - intersection_c.y))
			reference_4 = NSPoint(node.position.x - (node.position.x - intersection_c.x) / 3,
			                      node.position.y - (node.position.y - intersection_c.y) / 3)
			offcurve_4 = NSPoint((reference_3.x + reference_4.x) / 2, (reference_3.y + reference_4.y) / 2)

			path.nodes.insert(node.index + 1, GSNode(offcurve_3, OFFCURVE))
			path.nodes[node.index + 2].smooth = True
			path.nodes.insert(node.index + 1, GSNode(offcurve_4, OFFCURVE))
			intersection_c_node.type = CURVE

		if flat_top:
			# divide flat_top_size by the aperture
			move_factor = flat_top_size / aperture
			# if the move factor is larger than 1, skip
			if 1 > move_factor and flat_top_size > 0:
				# calculate the coordinate of the point which is on the line intersection_b to new_node_position, at a
				# percentage of move_factor away from new_node_position
				reference_1 = NSPoint(new_node_position.x - (new_node_position.x - intersection_b.x) * move_factor,
									  new_node_position.y - (new_node_position.y - intersection_b.y) * move_factor)
				# calculate the coordinate of the point which is on the line intersection_c to new_node_position, at a
				# percentage of move_factor away from new_node_position
				reference_2 = NSPoint(new_node_position.x - (new_node_position.x - intersection_c.x) * move_factor,
									  new_node_position.y - (new_node_position.y - intersection_c.y) * move_factor)
				# insert these nodes on the paths, one after the current node and one before
				path.insertNode_atIndex_(GSNode(reference_1), node.index)
				path.insertNode_atIndex_(GSNode(reference_2), node.index + 1)
			if flat_top_size > 0:
				path.removeNode_(node)
			if depth == 0:
				path.removeNode_(intersection_b_node)
				path.removeNode_(intersection_c_node)

	@objc.python_method
	def draw_calculations(self, layer, info):
		try:
			return
			NSColor.redColor().set()
			layer.bezierPath.fill()
		except:
			import traceback
			print(traceback.format_exc())

	def confirmDialog_(self, sender):
		objc.super(Inktrapeze, self).confirmDialog_(sender)
		Glyphs.removeCallback(self.draw_calculations)

	def cancelDialog_(self, sender):
		objc.super(Inktrapeze, self).cancelDialog_(sender)
		Glyphs.removeCallback(self.draw_calculations)

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
