import QtQuick 2.15

// PySign design system - modern, warm, accessible color palette.
QtObject {
    id: theme

    property bool isDark: true

    property string fontFamily: "Helvetica Neue"
    property int textXs: 12
    property int textSm: 14
    property int textMd: 16
    property int textLg: 18
    property int textXl: 22
    property int text2Xl: 30
    property int text3Xl: 44

    property int space1: 4
    property int space2: 8
    property int space3: 12
    property int space4: 16
    property int space5: 24
    property int space6: 32
    property int space7: 48

    property int radiusSm: 10
    property int radiusMd: 16
    property int radiusLg: 24
    property int radiusPill: 999

    // Dark mode: deep indigo base with cyan-mint accent
    function background()       { return isDark ? "#0A0E1A" : "#F8FAFC" }
    function surface()          { return isDark ? "#111827" : "#FFFFFF" }
    function surfaceRaised()    { return isDark ? "#1A2238" : "#F0F4FA" }
    function surfaceMuted()     { return isDark ? "#1F2A44" : "#E8EEF7" }
    function border()           { return isDark ? "#2A3A5C" : "#D8E1EE" }
    function text()             { return isDark ? "#F1F5FF" : "#0F1A2E" }
    function textMuted()        { return isDark ? "#8B9DC3" : "#5E6E8A" }
    function textFaint()        { return isDark ? "#5A6E9A" : "#8A98AD" }

    // Accent: vibrant cyan-mint
    function accent()           { return isDark ? "#00E5C7" : "#00B89C" }
    function accentStrong()     { return isDark ? "#00F5D1" : "#009E82" }
    function accentSoft()       { return isDark ? "#0A3D35" : "#D0FAF2" }

    // Success: warm emerald
    function success()          { return isDark ? "#34D399" : "#059669" }
    function successSoft()      { return isDark ? "#0A3D2E" : "#D1FAE5" }

    // Warning: warm amber
    function warning()          { return isDark ? "#FBBF24" : "#D97706" }
    function warningSoft()      { return isDark ? "#45320A" : "#FEF3C7" }

    // Danger: coral red (colorblind safe)
    function danger()           { return isDark ? "#FB7185" : "#DC2626" }
    function dangerSoft()       { return isDark ? "#4A1A22" : "#FEE2E2" }

    function stateColor(state) {
        if (state === "success") return success()
        if (state === "warning") return warning()
        if (state === "error") return danger()
        return accent()
    }

    function stateSurface(state) {
        if (state === "success") return successSoft()
        if (state === "warning") return warningSoft()
        if (state === "error") return dangerSoft()
        return accentSoft()
    }
}
