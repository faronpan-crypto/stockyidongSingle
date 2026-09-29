import Foundation

// MARK: - 持仓
struct Position: Codable, Identifiable, Hashable {
    let id: Int
    let code: String
    var name: String
    var buyPrice: Double
    var shares: Int
    let createdAt: String?
    let currentPrice: Double?
    let profit: Double?
    let profitPct: Double?

    enum CodingKeys: String, CodingKey {
        case id, code, name
        case buyPrice = "buy_price"
        case shares
        case createdAt = "created_at"
        case currentPrice = "current_price"
        case profit
        case profitPct = "profit_pct"
    }

    var displayProfit: String {
        guard let p = profit else { return "--" }
        let sign = p >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.0f", p))"
    }

    var displayProfitPct: String {
        guard let p = profitPct else { return "--" }
        let sign = p >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", p))%"
    }

    var isProfit: Bool { (profit ?? 0) >= 0 }
}

// MARK: - 持仓列表响应
struct PositionListResponse: Codable {
    let positions: [Position]
}

// MARK: - 新增持仓请求
struct AddPositionRequest: Codable {
    let code: String
    let name: String
    let buyPrice: Double
    let shares: Int

    enum CodingKeys: String, CodingKey {
        case code, name
        case buyPrice = "buy_price"
        case shares
    }
}

// MARK: - 通用响应
struct GeneralResponse: Codable {
    let success: Bool?
    let id: Int?
    let error: String?
}
