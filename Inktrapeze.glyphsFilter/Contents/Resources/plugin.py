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

from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import *
from GlyphsApp.plugins import *
from math import sqrt, dist, sin, acos, degrees, radians
from Foundation import NSPoint


class Inktrapeze(FilterWithDialog):

	# Definitions of IBOutlets

	# The NSView object from the User Interface. Keep this here!
	dialog = objc.IBOutlet()

	# Text field in dialog
	apertureTextField = objc.IBOutlet()
	depthSlider = objc.IBOutlet()
	curvedCheckbox = objc.IBOutlet()

	@objc.python_method
	def settings(self):
		self.menuName = Glyphs.localize({
			"en": "Inktrapeze",
			"de": "Inktrapeze",
			"fr": "Inktrapeze",
			"es": "Inktrapeze",
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
	def setDepth_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.depth"] = float(sender.floatValue())
		self.update()

	@objc.IBAction
	def setCurved_(self, sender):
		Glyphs.defaults["com.eweracs.inktrapeze.curved"] = bool(sender.state())
		self.update()

	@objc.python_method
	def set_fields(self):
		self.apertureTextField.setStringValue_(Glyphs.defaults["com.eweracs.inktrapeze.aperture"] or "20")
		self.depthSlider.setFloatValue_(Glyphs.defaults["com.eweracs.inktrapeze.depth"] or 1)
		self.curvedCheckbox.setState_(Glyphs.defaults["com.eweracs.inktrapeze.curved"] or False)

	# Actual filter
	@objc.python_method
	def filter(self, layer, inEditView, customParameters):
		aperture = Glyphs.defaults["com.eweracs.inktrapeze.aperture"]
		depth = Glyphs.defaults["com.eweracs.inktrapeze.depth"]
		curved = Glyphs.defaults["com.eweracs.inktrapeze.curved"]
		if not inEditView:
			return False
		for path in layer.paths:
			for node in path.nodes:
				if node.selected:
					self.create_inktrap_for_node(node, aperture, depth, curved)

	@objc.python_method
	def lerp(self, time, start, end):
		return NSPoint(int((1 - time) * start.x + time * end.x), int((1 - time) * start.y + time * end.y))

	@objc.python_method
	def create_inktrap_for_node(self, node, aperture, depth, curved):
		# there are three nodes that form a triangle. A center node ("node") and one left and one right node ("left_node" and
		# "right_node")

		path = node.parent
		layer = node.layer

		prev_node = node.prevNode
		next_node = node.nextNode

		if prev_node is None or next_node is None:
			print("Node is not connected to other nodes.")
			return
		if prev_node.type == "offcurve" or next_node.type == "offcurve":
			print("Node is an offcurve node.")
			return

		# calculate the distance between the left and right nodes
		a = dist([prev_node.position.x, prev_node.position.y], [next_node.position.x, next_node.position.y])
		# calculate the distance between the left node and the selected node
		b = dist([node.position.x, node.position.y], [prev_node.position.x, prev_node.position.y])
		# calculate the distance between the right node and the selected node
		c = dist([node.position.x, node.position.y], [next_node.position.x, next_node.position.y])

		# calculate the angle at the selected node
		angle_at_node = degrees(acos((b ** 2 + c ** 2 - a ** 2) / (2 * b * c)))

		# see how far into my angle the circle can be pushed, then calculate the intersections with b and c
		# if the angle is less than 90 degrees, the circle can be pushed inwards
		if angle_at_node < 90:
			# calculate the size of the other two equal angles in the triangle consisting of the intersection points of the
			# pushed-in circle and the selected node
			other_angles = (180 - angle_at_node) / 2
			# make a right triangle using the diameter of the circle as the hypotenuse. The right angle will be at the
			# intersection of the circle with line c.
			# calculate the angle on in the triangle at the intersection of the circle with line c
			circle_angle = 90 - other_angles
			# calculate the distance from the intersection of the circle with line c to the hypotenuse
			circle_line_b = sin(circle_angle)
			# calculate the distance from the intersection of the circle with line c to the intersection with line b
			line_between_intersections = sqrt(aperture ** 2 - circle_line_b ** 2)

			# using the angle A and the two other angles, as well as line_a as the line opposite angle A, calculate the
			# distance of the intersections to the selected node
			distance_to_intersections = line_between_intersections * sin(radians(other_angles)) / sin(
				radians(angle_at_node))

			# calculate the path time at which the intersection with line b is reached
			factor_b = distance_to_intersections / b
			# calculate the coordinates of intersection b using the coordinates of the selected node and of the left node
			intersection_b = NSPoint(node.position.x + (prev_node.position.x - node.position.x) * factor_b,
			                         node.position.y + (prev_node.position.y - node.position.y) * factor_b)
			# calculate the path time at which the intersection with line c is reached
			factor_c = distance_to_intersections / c
			# calculate the coordinates of intersection c using the coordinates of the selected node and of the right node
			intersection_c = NSPoint(node.position.x + (next_node.position.x - node.position.x) * factor_c,
			                         node.position.y + (next_node.position.y - node.position.y) * factor_c)

			path.insertNode_atIndex_(GSNode(intersection_b), node.index)
			path.insertNode_atIndex_(GSNode(intersection_c), node.index + 1)

			# open a corner at the node
			layer.openCornerAtNode_offset_(node, distance_to_intersections * depth)
			# find the middle between the two new nodes
			node_1_position = path.nodes[node.index].position
			node_2_position = path.nodes[node.index - 1].position
			middle_node = GSNode()
			middle_node.position = NSPoint(node_1_position.x + (node_2_position.x - node_1_position.x) / 2,
			                               node_1_position.y + (node_2_position.y - node_1_position.y) / 2)
			path.insertNode_atIndex_(middle_node, node.index)
			path.removeNodeAtIndex_(node.index - 2)
			path.removeNodeAtIndex_(node.index)

			# if curved:
			# 	offcurve_1 = GSNode(self.lerp(0.33,
			# 	                              path.nodes[middle_node.index - 1].position,
			# 	                              middle_node.position),
			# 	                    OFFCURVE)
			# 	offcurve_2 = GSNode(self.lerp(0.66,
			# 	                              path.nodes[middle_node.index - 1].position,
			# 	                              middle_node.position),
			# 	                    OFFCURVE)
			# 	path.nodes.insert(middle_node.index, offcurve_1)
			# 	path.nodes.insert(middle_node.index, offcurve_2)
			# 	middle_node.type = CURVE
			#
			# 	offcurve_3 = GSNode(self.lerp(0.33,
			# 	                              middle_node.position,
			# 	                              path.nodes[middle_node.index - 1].position),
			# 	                    OFFCURVE)
			# 	offcurve_4 = GSNode(self.lerp(0.66,
			# 	                              middle_node.position,
			# 	                              path.nodes[middle_node.index - 1].position),
			# 	                    OFFCURVE)
			# 	path.nodes.insert(middle_node.index, offcurve_3)
			# 	path.nodes.insert(middle_node.index, offcurve_4)


	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
