import QtQuick 2.15
import QtQuick.Controls 2.15

pragma Singleton

QtObject {
    id: theme

    // Colors - Dark theme (default)
    property color colorBackground: "#18181B"
    property color colorSurface: "#27272A"
    property color colorSurfaceVariant: "#3F3F46"
    property color colorSurfaceElevated: "#52525B"
    property color colorTextPrimary: "#FAFAFA"
    property color colorTextSecondary: "#A1A1AA"
    property color colorTextDisabled: "#71717A"
    property color colorTextOnAccent: "#18181B"
    property color colorAccent: "#22D3EE"
    property color colorAccentHover: "#06B6D4"
    property color colorAccentPressed: "#0891B2"
    property color colorSuccess: "#4ADE80"
    property color colorSuccessBg: "#14532D"
    property color colorError: "#F87171"
    property color colorErrorBg: "#7F1D1D"
    property color colorWarning: "#FBBF24"
    property color colorWarningBg: "#78350F"
    property color colorBorder: "#3F3F46"
    property color colorBorderFocus: "#22D3EE"
    property color colorDivider: "#3F3F46"

    // Skeleton colors
    property color skeletonCorrect: "#4ADE80"
    property color skeletonIncorrect: "#F87171"
    property color skeletonNeutral: "#A1A1AA"
    property color skeletonConnections: "#52525B"

    // Dwell
    property color dwellRingBg: "#3F3F46"
    property color dwellRingFill: "#22D3EE"

    // Spacing
    property int spacingXs: 4
    property int spacingSm: 8
    property int spacingMd: 16
    property int spacingLg: 24
    property int spacingXl: 32
    property int spacingXxl: 48

    // Radius
    property int radiusSm: 6
    property int radiusMd: 10
    property int radiusLg: 16
    property int radiusXl: 24
    property int radiusFull: 9999

    // Typography
    property string fontFamily: "'Inter', 'SF Pro Display', 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif"
    property int fontSizeXs: 12
    property int fontSizeSm: 14
    property int fontSizeBase: 16
    property int fontSizeLg: 18
    property int fontSizeXl: 20
    property int fontSizeXxl: 24
    property int fontSizeXxxl: 32
    property int fontWeightRegular: 400
    property int fontWeightMedium: 500
    property int fontWeightSemiBold: 600
    property int fontWeightBold: 700

    // Shadows
    property string shadowSm: "0 1px 2px rgba(0, 0, 0, 0.05)"
    property string shadowMd: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)"
    property string shadowLg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)"
    property string shadowXl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)"

    // Component tokens
    property int buttonHeight: 56
    property int buttonHeightSm: 44
    property int buttonPaddingH: 24
    property int iconSize: 24
    property int iconSizeLg: 32
    property int cameraMinWidth: 640
    property int cameraMinHeight: 480
    property int dwellDurationMs: 2000
    property int dwellCursorSize: 16
    property int dwellRingThickness: 4

    // Chart/Progress
    property int chartHeight: 200
    property int heatmapCellSize: 36

    // Theme switching
    property bool isDark: true

    function toggleTheme() {
        isDark = !isDark
    }

    // Light theme colors (computed when needed)
    property color colorBackgroundLight: "#FAFAFA"
    property color colorSurfaceLight: "#FFFFFF"
    property color colorSurfaceVariantLight: "#F4F4F5"
    property color colorSurfaceElevatedLight: "#E4E4E7"
    property color colorTextPrimaryLight: "#18181B"
    property color colorTextSecondaryLight: "#52525B"
    property color colorTextDisabledLight: "#A1A1AA"
    property color colorTextOnAccentLight: "#FAFAFA"
    property color colorAccentLight: "#06B6D4"
    property color colorAccentHoverLight: "#0891B2"
    property color colorAccentPressedLight: "#0E7490"
    property color colorSuccessLight: "#16A34A"
    property color colorSuccessBgLight: "#DCFCE7"
    property color colorErrorLight: "#DC2626"
    property color colorErrorBgLight: "#FEF2F2"
    property color colorWarningLight: "#D97706"
    property color colorWarningBgLight: "#FFFBEB"
    property color colorBorderLight: "#E4E4E7"
    property color colorBorderFocusLight: "#06B6D4"
    property color colorDividerLight: "#E4E4E7"
    property color skeletonCorrectLight: "#16A34A"
    property color skeletonIncorrectLight: "#DC2626"
    property color skeletonNeutralLight: "#71717A"
    property color skeletonConnectionsLight: "#D4D4D8"
    property color dwellRingBgLight: "#E4E4E7"
    property color dwellRingFillLight: "#06B6D4"
    property color colorBorderLight: "#E4E4E7"
    property color colorBorderFocusLight: "#06B6D4"
    property color colorDividerLight: "#E4E4E7"
    property color colorTextOnAccentLight: "#18181B"

    // Dynamic color getters based on theme
    function colorBackground() { return isDark ? colorBackground : colorBackgroundLight }
    function colorSurface() { return isDark ? colorSurface : colorSurfaceLight }
    function colorSurfaceVariant() { return isDark ? colorSurfaceVariant : colorSurfaceVariantLight }
    function colorSurfaceElevated() { return isDark ? colorSurfaceElevated : colorSurfaceElevatedLight }
    function colorTextPrimary() { return isDark ? colorTextPrimary : colorTextPrimaryLight }
    function colorTextSecondary() { return isDark ? colorTextSecondary : colorTextSecondaryLight }
    function colorTextDisabled() { return isDark ? colorTextDisabled : colorTextDisabledLight }
    function colorTextOnAccent() { return isDark ? colorTextOnAccent : colorTextOnAccentLight }
    function colorAccent() { return isDark ? colorAccent : colorAccentLight }
    function colorAccentHover() { return isDark ? colorAccentHover : colorAccentHoverLight }
    function colorAccentPressed() { return isDark ? colorAccentPressed : colorAccentPressedLight }
    function colorSuccess() { return isDark ? colorSuccess : colorSuccessLight }
    function colorSuccessBg() { return isDark ? colorSuccessBg : colorSuccessBgLight }
    function colorError() { return isDark ? colorError : colorErrorLight }
    function colorErrorBg() { return isDark ? colorErrorBg : colorErrorBgLight }
    function colorWarning() { return isDark ? colorWarning : colorWarningLight }
    function colorWarningBg() { return isDark ? colorWarningBg : colorWarningBgLight }
    function colorBorder() { return isDark ? colorBorder : colorBorderLight }
    function colorBorderFocus() { return isDark ? colorBorderFocus : colorBorderFocusLight }
    function colorDivider() { return isDark ? colorDivider : colorDividerLight }
    function skeletonCorrect() { return isDark ? skeletonCorrect : skeletonCorrectLight }
    function skeletonIncorrect() { return isDark ? skeletonIncorrect : skeletonIncorrectLight }
    function skeletonNeutral() { return isDark ? skeletonNeutral : skeletonNeutralLight }
    function skeletonConnections() { return isDark ? skeletonConnections : skeletonConnectionsLight }
    function dwellRingBg() { return isDark ? dwellRingBg : dwellRingBgLight }
    function dwellRingFill() { return isDark ? dwellRingFill : dwellRingFillLight }
    function colorTextOnAccent() { return isDark ? colorTextOnAccent : colorTextOnAccentLight }
    function colorBorder() { return isDark ? colorBorder : colorBorderLight }
    function colorBorderFocus() { return isDark ? colorBorderFocus : colorBorderFocusLight }
    function colorDivider() { return isDark ? colorDivider : colorDividerLight }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBackground() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorSurface() { return isDark ? "#27272A" : "#FFFFFF" }
    function colorSurfaceVariant() { return isDark ? "#3F3F46" : "#F4F4F5" }
    function colorSurfaceElevated() { return isDark ? "#52525B" : "#E4E4E7" }
    function colorTextPrimary() { return isDark ? "#FAFAFA" : "#18181B" }
    function colorTextSecondary() { return isDark ? "#A1A1AA" : "#52525B" }
    function colorTextDisabled() { return isDark ? "#71717A" : "#A1A1AA" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorAccent() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorAccentHover() { return isDark ? "#06B6D4" : "#0891B2" }
    function colorAccentPressed() { return isDark ? "#0891B2" : "#0E7490" }
    function colorSuccess() { return isDark ? "#4ADE80" : "#16A34A" }
    function colorSuccessBg() { return isDark ? "#14532D" : "#DCFCE7" }
    function colorError() { return isDark ? "#F87171" : "#DC2626" }
    function colorErrorBg() { return isDark ? "#7F1D1D" : "#FEF2F2" }
    function colorWarning() { return isDark ? "#FBBF24" : "#D97706" }
    function colorWarningBg() { return isDark ? "#78350F" : "#FFFBEB" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function skeletonCorrect() { return isDark ? "#4ADE80" : "#16A34A" }
    function skeletonIncorrect() { return isDark ? "#F87171" : "#DC2626" }
    function skeletonNeutral() { return isDark ? "#A1A1AA" : "#71717A" }
    function skeletonConnections() { return isDark ? "#52525B" : "#D4D4D8" }
    function dwellRingBg() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function dwellRingFill() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorTextOnAccent() { return isDark ? "#18181B" : "#FAFAFA" }
    function colorBorder() { return isDark ? "#3F3F46" : "#E4E4E7" }
    function colorBorderFocus() { return isDark ? "#22D3EE" : "#06B6D4" }
    function colorDivider() { return isDark ? "#3F3F46" : "#E4E4E7" }