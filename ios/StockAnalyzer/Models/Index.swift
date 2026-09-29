import Foundation

// MARK: - 指数实时行情
struct RealtimeIndex: Codable, Identifiable, Hashable {
    let id: String          // "sh000001"
    let name: String        // "上证指数"
    let price: Double?      // 当前价
    let pct: Double?        // 涨跌幅%
    let change: Double?     // 涨跌额
    let open: Double?       // 今开
    let high: Double?       // 今高
    let low: Double?        // 今低
    let prevClose: Double?  // 昨收

    var displayPrice: String {
        guard let price = price else { return "--" }
        return String(format: "%.2f", price)
    }

    var displayPct: String {
        guard let pct = pct else { return "--" }
        let sign = pct >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", pct))%"
    }

    var isUp: Bool { (pct ?? 0) > 0 }
    var isDown: Bool { (pct ?? 0) < 0 }
}

// MARK: - 指数日K线
struct IndexKline: Codable, Identifiable, Hashable {
    let id = UUID()
    let date: String
    let open: Double
    let close: Double
    let high: Double
    let low: Double
    let volume: Int
    let pctChg: Double?

    enum CodingKeys: String, CodingKey {
        case date, open, close, high, low, volume
        case pctChg = "pct_chg"
    }
}

// MARK: - 指数K线响应
struct IndexKlineResponse: Codable {
    let code: String
    let name: String
    let data: [IndexKline]
}
