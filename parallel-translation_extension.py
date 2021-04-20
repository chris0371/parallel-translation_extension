#!/usr/bin/env python
# coding=utf-8
#
# Copyright (C) 2021, Christian Vogt <vogtc@uni-hildesheim.de>
#
# recursiveFuseTransform() has originally been written by 
# Mark "Klowner" Riedesel
# see: https://github.com/Klowner/inkscape-applytransforms
#
# edgeResize() has been inspired by inkscape-round-corners extension by
# Juergen Weigert <jnweiger@gmail.com>
# see: https://github.com/jnweiger/inkscape-round-corners
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#


# This extension was written and tested using Inkscape V1.0.2 
# Most probably, it will not work on versions prior to V1.0
#
# Resources I found being useful and inspiring:
# https://gitlab.com/inkscape/extensions/-/wikis/My-First-Effect-Extension
# https://wiki.inkscape.org/wiki/index.php?title=Extension_subsystem  
# https://wiki.inkscape.org/wiki/index.php?title=Extensions:_INX_widgets_and_parameters
# https://inkscape.gitlab.io/extensions/documentation/inkex.html
# https://inkscape-extensions-guide.readthedocs.io/en/latest/inkex-modules.html#
# https://gitlab.com/inkscape/extensions


# The purpose of this extension is to help performing parallel
# translations of selected straight paths (lines). This is equivalent
# to changing the absolute X coordinate of a vertical line or changing 
# the absolute Y coordinate of a horizontal line, but for lines drawn
# in any angle. 
#
# The second purpose is to align a group of objects to such a line 
# drawn in any angle. This means: moving and rotating the group and
# adjust its width to match the line length.
#
# V0.1  2021-04-20 : initial version.
#

import math
import inkex
from inkex.paths import CubicSuperPath, Path
from inkex.transforms import Transform
from inkex.styles import Style

NULL_TRANSFORM = Transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


class ParallelTranlationExtension(inkex.EffectExtension):

    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--copyMode"     , type=str          , default="none", help="Move copy or original")
        pars.add_argument("--distance"     , type=float        , default=0     , help="Distance to move")
        pars.add_argument("--distUnit"     , type=str          , default="mm"  , help="Unit of the distance")
        pars.add_argument("--reverse"      , type=inkex.Boolean, default=False , help="Move in opposite direction")
        pars.add_argument("--useFixedAngle", type=inkex.Boolean, default=False , help="use fixed translation angle")
        pars.add_argument("--fixedAngle"   , type=float        , default=0     , help="Translation angle")
        pars.add_argument("--copyModeA"    , type=str          , default="none", help="Align copy or original")
        pars.add_argument("--lengthModeA"  , type=str          , default="none", help="Group length adjustment method")
        pars.add_argument("--colorA"       , type=int          , default=0     , help="Color of rotation center circle")
        pars.add_argument("--reverseA"     , type=inkex.Boolean, default=False , help="additinal group rotate by 180 degrees")


    def effect(self):
        pathCount = 0
        groupCount = 0
        for elem in self.svg.get_selected():
            if isinstance(elem, inkex.PathElement):
                pathCount += 1
            elif isinstance(elem, inkex.Group):
                groupCount += 1
                self.alignGroup = elem
            
        if self.options.tab == "align":
            if pathCount == 0 or groupCount == 0:
                raise inkex.AbortExtension("In alignment mode, please select a group and a path.")
            if groupCount > 1:
                raise inkex.AbortExtension("Sorry, we can align a single group only.")
            if pathCount > 1 and self.options.copyModeA != 'copy':
                raise inkex.AbortExtension("To align to multiple pathes at once, please choose to apply the alignment to copies of the group.")
        else:        
            if pathCount == 0:
                raise inkex.AbortExtension("Please select one path at least.")

        for elem in self.svg.get_selected():
            self.process_node(elem)
        

    @staticmethod
    def very_close(a, b):
        # two numbers are compared for (very close) numerical equality
        eps = 1e-9
        return abs(a-b) < eps


    def edgeResize(self, obj, length):
        bbox = obj.bounding_box()
        dx = (length - bbox.width) / 2
        
        # Iterate over all children of the group-object.
        # Find path nodes located at the left and right edges of the 
        # groups bounding box, and move these by 'dx' further to the
        # left or right. 
        for child in obj.iterchildren():

            if not isinstance(child, inkex.PathElement):
                continue  #ignore all non-path-objects

            csp = child.path.to_superpath()
            node_count = 0;
            for sub in csp:
                for node in sub:
                    node_x = node[1][0]
                    if self.very_close( node_x, bbox.left ):
                        node[1][0] -= dx
                        node_count += 1
                        """msg = "id:{} touched left edge at:{}"
                        self.msg(msg.format(child.get_id(), 
                                            bbox.left))"""

                    if self.very_close( node_x, bbox.right ):
                        node[1][0] += dx
                        node_count += 1
                        """msg = "id:{} touched right edge at:{}"
                        self.msg(msg.format(child.get_id(), 
                                            bbox.right))"""
                        
            if node_count > 0:
                # we've moved some nodes of this superpath! 
                # convert back to real path and modify child object in-place
                child.set_path(csp.to_path(curves_only=False))


    def align(self, x, y, alpha, length):
        rotation_col = inkex.Color(self.options.colorA).to_rgba()
        rotation_bb = None

        # select the object to move
        if self.options.copyModeA in ('copy'):
            objToMove = self.alignGroup.duplicate()
        else:
            if self.options.copyModeA in ('obj'):
                self.alignGroup.duplicate()
            objToMove = self.alignGroup        

        """
        msg = "align goup {}"
        self.msg(msg.format(self.alignGroup.get_id()))
        msg = " to: x={} y={}"
        self.msg(msg.format(x,y))
        msg = " length: {}"
        self.msg(msg.format(length))
        msg = " angle : {}"
        self.msg(msg.format(math.degrees(alpha)))
        msg = " rotation center color:{}"
        self.msg(msg.format(rotation_col))
        for child in self.alignGroup.iterchildren():
            bbox = child.bounding_box()
            msg = "    child-obj:{} fill:{} stroke:{} x={} y={}"
            self.msg(msg.format(child.get_id(), 
                                child.style.get_color(name='fill'),
                                child.style.get_color(name='stroke'),
                                bbox.x.center,
                                bbox.y.center))
        """
        # first, apply any transformations the object may have already
        # so we are starting with no transform assigned to the group
        self.recursiveFuseTransform(objToMove)
        
        # Adjust the objects length. Since we haven't moved or rotated
        # it by now, we have to adjust its width only.
        if self.options.lengthModeA != "none":
            if self.options.lengthModeA == "scale":
                tr = inkex.Transform()
                tr.add_scale( length / objToMove.bounding_box().width, 1 )
                objToMove.transform = tr * objToMove.transform
                self.recursiveFuseTransform(objToMove)
            elif self.options.lengthModeA == "endpoints":
                self.edgeResize( objToMove, length )
        
        # locate the rotation center marker in the object to move by 
        # checking for the rotation marker fill color within the group
        for child in objToMove.iterchildren():
            if child.style.get_color(name='fill') == rotation_col:
                rotation_bb = child.bounding_box()
        if rotation_bb is None:
            raise inkex.AbortExtension("No rotation center object found in group.")

        # then, move it to the desired location
        dx = x - rotation_bb.x.center
        dy = y - rotation_bb.y.center
        tr = inkex.Transform()
        tr.add_translate( dx, dy )
        objToMove.transform = tr * objToMove.transform
        self.recursiveFuseTransform(objToMove)

        # finally, rotate it by the given angle at the desired location        
        tr = inkex.Transform()
        tr.add_rotate( math.degrees(alpha), x, y )
        objToMove.transform = tr * objToMove.transform
        self.recursiveFuseTransform(objToMove)


    def process_node(self, elem):
        if not isinstance(elem, inkex.PathElement):
            return # just ignore all non-path elements
        
        for sub in elem.path.to_superpath():            
            # Calculate the objects rotation angle alpha.
            # A horizontal line from left to right is 0 degrees.
            # Positive angles means the line is rotated clockwise.
            # -180 < alpha <= +180
            x1=sub[0][1][0]
            y1=sub[0][1][1]
            x2=sub[-1][1][0]
            y2=sub[-1][1][1]
            width = x2-x1
            heigth= y2-y1
            if self.very_close( width, 0 ):
                if heigth > 0:
                    alpha = math.pi/2
                else:
                    alpha = -math.pi/2
            else:
                alpha = math.atan(heigth/width)
                if width < 0:
                    if heigth < 0:
                        alpha -= math.pi
                    else:
                        alpha += math.pi
            xm = (x1+x2)/2
            ym = (y1+y2)/2
            length = math.sqrt( math.pow(width,2) + math.pow(heigth,2) )

            # Select translation angle by options
            if self.options.useFixedAngle:
                da = math.radians(self.options.fixedAngle)
            else:
                da = alpha

            # Calculate translation in x and y direction
            # A positive distance value moves towards greater coordinates
            dist = self.svg.unittouu('{}{}'.format(self.options.distance, 
                                                   self.options.distUnit) )
            if self.options.reverse:
                da = da + math.radians(180)
            dx = -math.sin(da) * dist
            dy = math.cos(da) * dist

            if self.options.tab in ('translation'):
                if self.options.copyMode in ('copy'):
                    objToMove = elem.duplicate()
                else:
                    if self.options.copyMode in ('obj'):
                        elem.duplicate()
                    objToMove = elem
                objToMove.path = objToMove.path.translate( dx, dy )
            
            elif self.options.tab in ('align'):
                if self.options.reverseA:
                    alpha = alpha + math.radians(180)
                self.align(xm, ym, alpha, length)
            
            else:
                msg = "Measuring result:"
                self.msg(msg)
                msg = " object name: {}"
                self.msg(msg.format(elem.get_id()))
                msg = " start point: x={} y={}"
                self.msg(msg.format(x1,y1))
                msg = " end point:   x={} y={}"
                self.msg(msg.format(x2,y2))
                msg = " mid point:   x={} y={}"
                self.msg(msg.format(xm,ym))
                msg = " object length: {}"
                self.msg(msg.format(length))
                msg = " object angle     : {}°"
                self.msg(msg.format(math.degrees(alpha)))
                msg = " translation angle: {}°"
                self.msg(msg.format(math.degrees(da)))
                msg = " translation:   dx={} dy={}"
                self.msg(msg.format(dx,dy))
                exit()


    @staticmethod
    def objectToPath(node):
        if node.tag == inkex.addNS('g', 'svg'):
            return node

        if node.tag == inkex.addNS('path', 'svg') or node.tag == 'path':
            for attName in node.attrib.keys():
                if ("sodipodi" in attName) or ("inkscape" in attName):
                    del node.attrib[attName]
            return node

        return node


    def recursiveFuseTransform(self, node, transf=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):

        transf = Transform(transf) * Transform(node.get("transform", None))

        if 'transform' in node.attrib:
            del node.attrib['transform']

        node = self.objectToPath(node)

        if transf == NULL_TRANSFORM:
            # Don't do anything if there is effectively no transform applied
            # reduces alerts for unsupported nodes
            pass
        elif 'd' in node.attrib:
            d = node.get('d')
            p = CubicSuperPath(d)
            p = Path(p).to_absolute().transform(transf, True)
            node.set('d', str(Path(CubicSuperPath(p).to_path())))

        elif node.tag in [inkex.addNS('polygon', 'svg'),
                          inkex.addNS('polyline', 'svg')]:
            points = node.get('points')
            points = points.strip().split(' ')
            for k, p in enumerate(points):
                if ',' in p:
                    p = p.split(',')
                    p = [float(p[0]), float(p[1])]
                    p = transf.apply_to_point(p)
                    p = [str(p[0]), str(p[1])]
                    p = ','.join(p)
                    points[k] = p
            points = ' '.join(points)
            node.set('points', points)

        elif node.tag in [inkex.addNS("ellipse", "svg"), inkex.addNS("circle", "svg")]:

            def isequal(a, b):
                return abs(a - b) <= transf.absolute_tolerance

            if node.TAG == "ellipse":
                rx = float(node.get("rx"))
                ry = float(node.get("ry"))
            else:
                rx = float(node.get("r"))
                ry = rx

            cx = float(node.get("cx"))
            cy = float(node.get("cy"))
            sqxy1 = (cx - rx, cy - ry)
            sqxy2 = (cx + rx, cy - ry)
            sqxy3 = (cx + rx, cy + ry)
            newxy1 = transf.apply_to_point(sqxy1)
            newxy2 = transf.apply_to_point(sqxy2)
            newxy3 = transf.apply_to_point(sqxy3)

            node.set("cx", (newxy1[0] + newxy3[0]) / 2)
            node.set("cy", (newxy1[1] + newxy3[1]) / 2)
            edgex = math.sqrt(
                abs(newxy1[0] - newxy2[0]) ** 2 + abs(newxy1[1] - newxy2[1]) ** 2
            )
            edgey = math.sqrt(
                abs(newxy2[0] - newxy3[0]) ** 2 + abs(newxy2[1] - newxy3[1]) ** 2
            )

            if not isequal(edgex, edgey) and (
                node.TAG == "circle"
                or not isequal(newxy2[0], newxy3[0])
                or not isequal(newxy1[1], newxy2[1])
            ):
                inkex.utils.errormsg(
                    "Warning: Shape %s (%s) is approximate only, try Object to path first for better results"
                    % (node.TAG, node.get("id"))
                )

            if node.TAG == "ellipse":
                node.set("rx", edgex / 2)
                node.set("ry", edgey / 2)
            else:
                node.set("r", edgex / 2)

        elif node.tag in [inkex.addNS('rect', 'svg'),
                          inkex.addNS('text', 'svg'),
                          inkex.addNS('image', 'svg'),
                          inkex.addNS('use', 'svg')]:
            inkex.utils.errormsg(
                "Shape %s (%s) not yet supported, try Object to path first"
                % (node.TAG, node.get("id"))
            )

        for child in node.getchildren():
            self.recursiveFuseTransform(child, transf)


if __name__ == '__main__':
    ParallelTranlationExtension().run()
