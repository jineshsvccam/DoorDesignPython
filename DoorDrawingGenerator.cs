using netDxf;
using netDxf.Entities;
using netDxf.Tables;

namespace DoorDesign
{
    /// <summary>
    /// Utility class to generate DXF drawings for door sheet cutting and annotations.
    /// The class creates an outer sheet rectangle, inner opening rectangle, holes and a center cutout,
    /// and adds dimension annotations for manufacturing.
    /// </summary>
    class DoorDrawingGenerator
    {
        // Constants / default values used across the drawing generation
        private const double DefaultBendAdjust = 12.0;
        private const double DefaultBoxGap = 30.0;
        private const double DefaultBoxWidth = 22.0;
        private const double DefaultBoxHeight = 112.0;
        private const double DefaultCircleRadius = 5.0;
        private const double DefaultLeftCircleOffset = 40.0;
        private const double DefaultTopCircleOffset = 150.0;
        private const double DimTextHeight = 8.0;
        private const double DimArrowSize = 6.0;
        private const double HorizontalDimVisualOffset = 20.0;
        private const double VerticalDimVisualOffset = 40.0;

        /// <summary>
        /// Generates a DXF file that contains outer sheet cut, inner opening, two circles and a center box with dimensions.
        /// Input units are preserved (e.g., mm if the input values are in mm).
        /// </summary>
        public static void GenerateDoorDxf(
            double widthMeasurement,
            double heightMeasurement,
            double leftSideAllowanceWidth,
            double rightSideAllowanceWidth,
            double leftSideAllowanceHeight,
            double rightSideAllowanceHeight,
            double doorMinusMeasurementWidth,
            double doorMinusMeasurementHeight,
            double bendingWidth,
            double bendingHeight,
            string fileName)
        {
            // --- Derived geometry ---
            double frameTotalWidth = widthMeasurement + leftSideAllowanceWidth + rightSideAllowanceWidth;
            double frameTotalHeight = heightMeasurement + leftSideAllowanceHeight + rightSideAllowanceHeight;

            // inner opening (the opening to be cut from the sheet)
            double innerWidth = frameTotalWidth - doorMinusMeasurementWidth;
            double innerHeight = frameTotalHeight - doorMinusMeasurementHeight;

            // outer (sheet) dimensions include bending allowances in width only (outer height intentionally equals innerHeight)
            double outerWidth = innerWidth + bendingWidth;
            double outerHeight = innerHeight; // outer height matches inner opening height in this layout

            // Bend-related adjustments used to position inner rectangle relative to outer sheet
            double bendAdjust = DefaultBendAdjust;

            // Inner rectangle offsets (position of inner rectangle relative to outer origin)
            double innerOffsetX = bendingWidth - bendAdjust;
            double innerOffsetY = bendAdjust - bendingHeight; // may be negative to indicate inner rectangle below outer origin

            // --- DXF setup ---
            var dxf = new DxfDocument();
            var cutLayer = new Layer("CUT") { Color = AciColor.Cyan };
            var dimLayer = new Layer("DIMENSIONS") { Color = AciColor.Red };

            // Outer sheet rectangle (clockwise)
            var outerRect = new Polyline2D(new List<Vector2>
            {
                new Vector2(0, 0),
                new Vector2(outerWidth, 0),
                new Vector2(outerWidth, outerHeight),
                new Vector2(0, outerHeight)
            }, true) { Layer = cutLayer };
            dxf.Entities.Add(outerRect);

            AddOuterBoxDimensions(dxf, outerWidth, outerHeight, dimLayer);

            // Inner opening rectangle (clockwise)
            var innerRect = new Polyline2D(new List<Vector2>
            {
                new Vector2(innerOffsetX, innerOffsetY),
                new Vector2(innerOffsetX + innerWidth, innerOffsetY),
                new Vector2(innerOffsetX + innerWidth, innerOffsetY + innerHeight + bendingHeight),
                new Vector2(innerOffsetX, innerOffsetY + innerHeight + bendingHeight)
            }, true) { Layer = cutLayer };
            dxf.Entities.Add(innerRect);

            // Add inner opening top and right dimensions
            AddInnerBoxDimensions(dxf, innerOffsetX, innerOffsetY, innerWidth, innerHeight, bendingHeight, dimLayer);

            // Add gap dimensions between inner opening and outer sheet (top/right/bottom/left as needed)
            AddInnerBoxGapDimensions(dxf, outerWidth, outerHeight, innerOffsetX, innerOffsetY, innerWidth, innerHeight, bendingHeight, dimLayer);

            // --- Circles (holes) with dimensions ---
            double circleRadius = DefaultCircleRadius;
            double leftCircleOffset = DefaultLeftCircleOffset;
            double topCircleOffset = DefaultTopCircleOffset;

            double circleCenterX = innerOffsetX + leftCircleOffset;
            double circleCenterYTop = innerHeight - topCircleOffset + innerOffsetY + bendAdjust;
            double circleCenterYBottom = topCircleOffset + innerOffsetY + bendAdjust;

            // Calculate vertical references and measured distances for labels
            double innerTopY = innerHeight;
            double innerBottomY = 0;
            double distFromTopToCircleTop = Math.Abs(innerTopY - circleCenterYTop);
            double distFromBottomToCircleBottom = Math.Abs(circleCenterYBottom - innerBottomY);

            AddCircleWithDimensions(dxf, circleCenterX, circleCenterYTop, circleRadius, innerOffsetX, innerTopY, $"{leftCircleOffset}", $"{Math.Round(distFromTopToCircleTop)}", cutLayer, dimLayer);
            AddCircleWithDimensions(dxf, circleCenterX, circleCenterYBottom, circleRadius, innerOffsetX, innerBottomY, $"{leftCircleOffset}", $"{Math.Round(distFromBottomToCircleBottom)}", cutLayer, dimLayer);

            // --- Center cutout box and its dimensions ---
            AddCenterBoxWithDimensions(dxf, innerOffsetX, innerOffsetY, innerHeight + bendingHeight, outerHeight, cutLayer, dimLayer);

            // Save DXF
            dxf.Save(fileName);
            Console.WriteLine($"DXF file '{fileName}' created successfully.");
        }

        // Adds a generic linear dimension between two points. Supports horizontal and vertical dimensions.
        private static void AddLinearDimension(
            DxfDocument dxf,
            Vector2 measureStart,
            Vector2 measureEnd,
            double offset,
            string label,
            bool isHorizontal,
            Layer dimLayer,
            double textHeight = DimTextHeight,
            double arrowSize = DimArrowSize)
        {
            if (measureStart.Equals(measureEnd)) return;

            if (isHorizontal)
            {
                double dimY = measureStart.Y + offset;
                var dimStart = new Vector2(measureStart.X, dimY);
                var dimEnd = new Vector2(measureEnd.X, dimY);

                dxf.Entities.Add(new Line(dimStart, dimEnd) { Layer = dimLayer });
                dxf.Entities.Add(new Line(measureStart, new Vector2(measureStart.X, dimY)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(measureEnd, new Vector2(measureEnd.X, dimY)) { Layer = dimLayer });

                // Arrows
                dxf.Entities.Add(new Line(dimStart, new Vector2(dimStart.X + arrowSize, dimStart.Y + arrowSize / 2)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimStart, new Vector2(dimStart.X + arrowSize, dimStart.Y - arrowSize / 2)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimEnd, new Vector2(dimEnd.X - arrowSize, dimEnd.Y + arrowSize / 2)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimEnd, new Vector2(dimEnd.X - arrowSize, dimEnd.Y - arrowSize / 2)) { Layer = dimLayer });

                double midX = (measureStart.X + measureEnd.X) / 2.0;
                double textY = dimY + Math.Sign(offset) * (textHeight + 4);
                dxf.Entities.Add(new Text(label, new Vector3(midX, textY, 0), textHeight)
                {
                    Alignment = TextAlignment.MiddleCenter,
                    Layer = dimLayer
                });
            }
            else
            {
                double dimX = measureStart.X + offset;
                var dimStart = new Vector2(dimX, measureStart.Y);
                var dimEnd = new Vector2(dimX, measureEnd.Y);

                dxf.Entities.Add(new Line(dimStart, dimEnd) { Layer = dimLayer });
                dxf.Entities.Add(new Line(measureStart, new Vector2(dimX, measureStart.Y)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(measureEnd, new Vector2(dimX, measureEnd.Y)) { Layer = dimLayer });

                // Arrows
                dxf.Entities.Add(new Line(dimStart, new Vector2(dimStart.X - arrowSize / 2, dimStart.Y + arrowSize)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimStart, new Vector2(dimStart.X + arrowSize / 2, dimStart.Y + arrowSize)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimEnd, new Vector2(dimEnd.X - arrowSize / 2, dimEnd.Y - arrowSize)) { Layer = dimLayer });
                dxf.Entities.Add(new Line(dimEnd, new Vector2(dimEnd.X + arrowSize / 2, dimEnd.Y - arrowSize)) { Layer = dimLayer });

                double midY = (measureStart.Y + measureEnd.Y) / 2.0;
                double textX = dimX + Math.Sign(offset) * (textHeight + 4);
                dxf.Entities.Add(new Text(label, new Vector3(textX, midY, 0), textHeight)
                {
                    Alignment = Math.Sign(offset) >= 0 ? TextAlignment.MiddleLeft : TextAlignment.MiddleRight,
                    Layer = dimLayer
                });
            }
        }

        // Outer sheet dimensions (left, bottom)
        private static void AddOuterBoxDimensions(
            DxfDocument dxf,
            double outerWidth,
            double outerHeight,
            Layer dimLayer,
            double offset = 20)
        {
            // bottom width
            AddLinearDimension(dxf, new Vector2(0, 0), new Vector2(outerWidth, 0), -offset, $"{outerWidth}", true, dimLayer);
            // left height
            AddLinearDimension(dxf, new Vector2(0, 0), new Vector2(0, outerHeight), -offset, $"{outerHeight}", false, dimLayer);
        }

        // Inner opening top (width) and right (height) dimensions
        private static void AddInnerBoxDimensions(
            DxfDocument dxf,
            double innerOffsetX,
            double innerOffsetY,
            double innerWidth,
            double innerHeight,
            double bendingHeight,
            Layer dimLayer,
            double offset = 20)
        {
            double topY = innerOffsetY + innerHeight + bendingHeight;
            AddLinearDimension(dxf, new Vector2(innerOffsetX, topY), new Vector2(innerOffsetX + innerWidth, topY), offset, $"{innerWidth}", true, dimLayer);

            double rightX = innerOffsetX + innerWidth;
            double totalInnerHeight = innerHeight + bendingHeight;
            AddLinearDimension(dxf, new Vector2(rightX, innerOffsetY), new Vector2(rightX, innerOffsetY + totalInnerHeight), offset * 2, $"{totalInnerHeight}", false, dimLayer);
        }

        // Add gap dimensions between inner opening and outer sheet. Top/right/bottom/left handled where appropriate.
        private static void AddInnerBoxGapDimensions(
            DxfDocument dxf,
            double outerWidth,
            double outerHeight,
            double innerOffsetX,
            double innerOffsetY,
            double innerWidth,
            double innerHeight,
            double bendingHeight,
            Layer dimLayer,
            double offset = 20)
        {
            // top-left horizontal gap measured along outer top
            AddLinearDimension(dxf, new Vector2(0, outerHeight), new Vector2(innerOffsetX, outerHeight), offset, $"{innerOffsetX}", true, dimLayer);

            // top-right horizontal gap measured along outer top
            double rightGap = outerWidth - (innerOffsetX + innerWidth);
            AddLinearDimension(dxf, new Vector2(innerOffsetX + innerWidth, outerHeight), new Vector2(outerWidth, outerHeight), offset, $"{rightGap}", true, dimLayer);

            // vertical gap at right: distance from inner top (including bending) to outer top
            double innerTop = innerOffsetY + innerHeight + bendingHeight;
            double topGap = Math.Abs(outerHeight - innerTop);
            AddLinearDimension(dxf, new Vector2(outerWidth, Math.Min(outerHeight, innerTop)), new Vector2(outerWidth, Math.Max(outerHeight, innerTop)), offset * 2, $"{Math.Round(topGap)}", false, dimLayer);

            // bottom vertical gap: distance from inner bottom to outer bottom
            double bottomGap = Math.Abs(innerOffsetY);
            AddLinearDimension(dxf, new Vector2(outerWidth, innerOffsetY), new Vector2(outerWidth, 0), offset * 2, $"{Math.Round(bottomGap)}", false, dimLayer);
        }

        // Draw circle and add horizontal/vertical dimension lines for its center
        private static void AddCircleWithDimensions(
            DxfDocument dxf,
            double centerX,
            double centerY,
            double radius,
            double refX,
            double refY,
            string horizLabel,
            string vertLabel,
            Layer cutLayer,
            Layer dimLayer)
        {
            dxf.Entities.Add(new Circle(new Vector3(centerX, centerY, 0), radius) { Layer = cutLayer });
            var center = new Vector2(centerX, centerY);

            // horizontal dimension from reference X to circle center
            AddLinearDimension(dxf, new Vector2(refX, centerY), center, HorizontalDimVisualOffset, horizLabel, true, dimLayer);

            // vertical dimension from reference Y to circle center
            AddLinearDimension(dxf, new Vector2(centerX, refY), center, VerticalDimVisualOffset, vertLabel, false, dimLayer);
        }

        // Center box cutout and its dimensions
        private static void AddCenterBoxWithDimensions(
            DxfDocument dxf,
            double innerOffsetX,
            double innerOffsetY,
            double innerTotalHeight,
            double outerHeight,
            Layer cutLayer,
            Layer dimLayer,
            double offset = 20)
        {
            double boxGap = DefaultBoxGap; // distance from inner left to box left
            double boxWidth = DefaultBoxWidth;
            double boxHeight = DefaultBoxHeight;

            double boxLeftX = innerOffsetX + boxGap;
            double boxBottomY = innerOffsetY + (innerTotalHeight - boxHeight) / 2.0;

            var boxRect = new Polyline2D(new List<Vector2>
            {
                new Vector2(boxLeftX, boxBottomY),
                new Vector2(boxLeftX + boxWidth, boxBottomY),
                new Vector2(boxLeftX + boxWidth, boxBottomY + boxHeight),
                new Vector2(boxLeftX, boxBottomY + boxHeight)
            }, true) { Layer = cutLayer };
            dxf.Entities.Add(boxRect);

            // dimension: gap from inner left to box left
            AddLinearDimension(dxf, new Vector2(innerOffsetX, boxBottomY + boxHeight), new Vector2(boxLeftX, boxBottomY + boxHeight), offset, $"{boxGap}", true, dimLayer);
            // dimension: box width
            AddLinearDimension(dxf, new Vector2(boxLeftX, boxBottomY + boxHeight), new Vector2(boxLeftX + boxWidth, boxBottomY + boxHeight), offset, $"{boxWidth}", true, dimLayer);
            // dimension: box height
            AddLinearDimension(dxf, new Vector2(boxLeftX + boxWidth, boxBottomY), new Vector2(boxLeftX + boxWidth, boxBottomY + boxHeight), offset * 2, $"{boxHeight}", false, dimLayer);

            // distance from top of center box to top of outer rectangle
            double topOfBox = boxBottomY + boxHeight;
            double topGap = outerHeight - topOfBox;
            AddLinearDimension(dxf, new Vector2(boxLeftX + boxWidth, topOfBox), new Vector2(boxLeftX + boxWidth, outerHeight), offset * 2, $"{Math.Round(topGap)}", false, dimLayer);
        }
    }
}