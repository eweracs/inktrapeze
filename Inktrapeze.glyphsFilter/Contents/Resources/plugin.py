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
from GlyphsApp import *
from GlyphsApp.plugins import *
from math import sqrt, dist, sin, acos, degrees, radians, pi
from Foundation import NSPoint


class Inktrapeze(FilterWithDialog):

	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()

	# Text field in dialog
	apertureTextField = objc.IBOutlet()
	thresholdSlider = objc.IBOutlet()
	depthSlider = objc.IBOutlet()
	straightRadio = objc.IBOutlet()
	curvedRadio = objc.IBOutlet()
	flatTopRadio = objc.IBOutlet()
	flatTopSizeTextField = objc.IBOutlet()

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
		self.set_fields()
		# Set focus to text field
		self.apertureTextField.becomeFirstResponder()

	@objc.IBAction
	def setAperture_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.aperture"] = float(sender.floatValue())
		self.update()

	@objc.IBAction
	def setThreshold_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.threshold"] = float(sender.floatValue())
		self.update()

	@objc.IBAction
	def setDepth_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.depth"] = float(sender.floatValue())
		self.update()

	@objc.IBAction
	def setStraight_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = bool(sender.state())
		self.curvedRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = False
		self.flatTopRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = False
		self.flatTopSizeTextField.setEnabled_(False)
		self.update()

	@objc.IBAction
	def setCurved_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = bool(sender.state())
		self.straightRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = False
		self.flatTopRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = False
		self.flatTopSizeTextField.setEnabled_(False)
		self.update()

	@objc.IBAction
	def setFlatTop_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] = bool(sender.state())
		self.straightRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.straight"] = False
		self.curvedRadio.setState_(False)
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = False
		self.flatTopSizeTextField.setEnabled_(True)
		self.update()

	@objc.IBAction
	def setFlatTopSize_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.flatTopSize"] = float(sender.floatValue())
		self.update()

	@objc.python_method
	def set_fields(self):
		self.apertureTextField.setStringValue_(Glyphs.defaults["com.eweracs.inktrapeze.aperture"] or "20")
		self.thresholdSlider.setFloatValue_(Glyphs.defaults["com.eweracs.inktrapeze.threshold"] or 0)
		self.depthSlider.setFloatValue_(Glyphs.defaults["com.eweracs.inktrapeze.depth"] or 0)
		self.straightRadio.setState_(Glyphs.defaults["com.eweracs.inktrapeze.straight"] or False)
		self.curvedRadio.setState_(Glyphs.defaults["com.eweracs.inktrapeze.curved"] or False)
		self.flatTopRadio.setState_(Glyphs.defaults["com.eweracs.inktrapeze.flatTop"] or False)
		self.flatTopSizeTextField.setStringValue_(Glyphs.defaults["com.eweracs.inktrapeze.flatTopSize"] or "10")

	# Actual filter
	@objc.python_method
	def filter(self, layer, inEditView, customParameters):
		aperture = float(self.apertureTextField.floatValue())
		threshold = 3 - float(self.thresholdSlider.floatValue())
		depth = float(self.depthSlider.floatValue())
		straight = bool(self.straightRadio.state())
		curved = bool(self.curvedRadio.state())
		flat_top = bool(self.flatTopRadio.state())
		flat_top_size = float(self.flatTopSizeTextField.floatValue())

		if not inEditView:
			return False
		for path in layer.paths:
			for node in path.nodes:
				if node.selected:
					self.create_inktrap_for_node(node, aperture, threshold, depth, straight, curved, flat_top,
												 flat_top_size)

	@objc.python_method
	def create_inktrap_for_node(self, node, aperture, threshold, depth, straight=True, curved=False, flat_top=False,
								flat_top_size=5):
		# there are three nodes that form a triangle. A center node ("node") and one left and one right node ("left_node" and
		# "right_node")

		path = node.parent

		prev_node = node.prevNode
		next_node = node.nextNode

		if prev_node is None or next_node is None:
			print("Node is not connected to other nodes.")
			return
		if prev_node.type == "offcurve" or next_node.type == "offcurve":
			print("Node is an offcurve node.")
			return

		# calculate the distance between the left and right node
		dist_prev_node_to_next_node = dist([prev_node.position.x, prev_node.position.y],
		                                   [next_node.position.x, next_node.position.y])
		# calculate the distance between the left node and the selected node
		dist_current_node_to_prev_node = dist([node.position.x, node.position.y],
		                                      [prev_node.position.x, prev_node.position.y])
		# calculate the distance between the right node and the selected node
		dist_current_node_next_node = dist([node.position.x, node.position.y],
		                                   [next_node.position.x, next_node.position.y])

		# calculate the angle at the selected node
		angle_at_current_node = degrees(acos((dist_current_node_to_prev_node ** 2 + dist_current_node_next_node ** 2 -
		                                      dist_prev_node_to_next_node ** 2) / (2 * dist_current_node_to_prev_node *
		                                                                           dist_current_node_next_node)))

		# see how far into the angle at the selected node the circle can be pushed, then calculate the intersections
		# of the circle with the left line and right line
		# calculate the size of the other two equal angles in the triangle which consists of the intersection points
		# and the selected node
		other_angles = (180 - angle_at_current_node) / 2
		# make a right triangle using the diameter of the circle as the hypotenuse. The right angle will be at the
		# intersection of the circle with the right line.
		# calculate the angle in the triangle at the intersection of the circle with the right line
		circle_angle = 90 - other_angles
		# calculate the distance from the intersection of the circle with right line to the hypotenuse
		circle_line_b = sin(circle_angle)
		# calculate the distance from the intersection of the circle with right line to the intersection with left line
		dist_between_intersections = sqrt(aperture ** 2 - circle_line_b ** 2)

		# using the angle at node and the two other angles, as well as the line connecting the prev and next node,
		# calculate the distance of the intersections to the selected node
		dist_node_to_intersections = dist_between_intersections * sin(radians(other_angles)) / sin(radians(
			angle_at_current_node))

		# calculate the path time at which the intersection with line b is reached
		factor_b = dist_node_to_intersections / dist_current_node_to_prev_node
		# calculate the coordinates of intersection b using the coordinates of the selected node and of the left node
		intersection_b = NSPoint(node.position.x + (prev_node.position.x - node.position.x) * factor_b,
		                         node.position.y + (prev_node.position.y - node.position.y) * factor_b)
		# calculate the path time at which the intersection with line c is reached
		factor_c = dist_node_to_intersections / dist_current_node_next_node
		# calculate the coordinates of intersection c using the coordinates of the selected node and of the right node
		intersection_c = NSPoint(node.position.x + (next_node.position.x - node.position.x) * factor_c,
		                         node.position.y + (next_node.position.y - node.position.y) * factor_c)

		# find center of line between intersections
		center_between_intersections = NSPoint((intersection_b.x + intersection_c.x) / 2,
		                                       (intersection_b.y + intersection_c.y) / 2)

		# find area of circle with aperture as diameter
		circle_area = (aperture / 2) ** 2 * pi

		# find area of triangle of intersection points and selected node
		semi_perimeter = (dist_between_intersections + dist_node_to_intersections * 2) / 2
		triangle_area = abs(sqrt(semi_perimeter * (semi_perimeter - dist_between_intersections)
								 * (semi_perimeter - dist_node_to_intersections) ** 2))

		# check whether the circle area multiplied by the threshold is larger than the triangle area
		threshold_area = abs(circle_area * threshold)
		if threshold_area < triangle_area:
			print("Threshold is too low. The circle will not fit in the triangle.")
			print(threshold_area, triangle_area)
			return

		intersection_b_node = GSNode(intersection_b)
		intersection_c_node = GSNode(intersection_c)
		path.insertNode_atIndex_(intersection_b_node, node.index)
		path.insertNode_atIndex_(intersection_c_node, node.index + 1)

		# calculate the position of a new node which is on an extension of the line from the center of the
		# intersections to the selected node
		new_node_position = NSPoint(node.position.x - (center_between_intersections.x - node.position.x) * depth,
									node.position.y - (center_between_intersections.y - node.position.y) * depth)

		node.position = new_node_position

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
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
