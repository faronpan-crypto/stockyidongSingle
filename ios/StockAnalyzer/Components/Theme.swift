import SwiftUI

// MARK: - App 主题颜色（深色模式）
extension Color {
    // 背景
    static let appBackground = Color.black           // #000000
    static let cardBackground = Color(red: 0.11, green: 0.11, blue: 0.12) // #1C1C1E
    static let sheetBackground = Color(red: 0.17, green: 0.17, blue: 0.18) // #2C2C2E

    // 文字
    static let textPrimary = Color.white
    static let textSecondary = Color(red: 0.55, green: 0.55, blue: 0.58) // #8E8E93
    static let textTertiary = Color(red: 0.35, green: 0.35, blue: 0.38)

    // 股票颜色（iOS 风格：绿涨红跌）
    static let stockUp = Color(red: 0.19, green: 0.82, blue: 0.35)     // #30D158
    static let stockDown = Color(red: 1.0, green: 0.27, blue: 0.22)    // #FF453A
    static let stockFlat = Color(red: 0.55, green: 0.55, blue: 0.58)    // #8E8E93

    // 预警
    static let warningRed = Color(red: 1.0, green: 0.27, blue: 0.22)   // #FF453A
    static let warningYellow = Color(red: 1.0, green: 0.84, blue: 0.04) // #FFD60A
    static let warningGreen = Color(red: 0.19, green: 0.82, blue: 0.35) // #30D158

    // 强调色
    static let accentBlue = Color(red: 0.04, green: 0.52, blue: 1.0)   // #0A84FF
}

// MARK: - 辅助扩展
extension Color {
    /// 涨跌颜色
    static func pctColor(_ value: Double) -> Color {
        if value > 0 { return .stockUp }
        if value < 0 { return .stockDown }
        return .stockFlat
    }
}
