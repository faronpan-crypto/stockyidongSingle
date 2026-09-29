import Foundation

// MARK: - 大跌预警信号
struct CrashSignal: Codable, Identifiable, Hashable {
    let id = UUID()
    let name: String
    let value: Int?
    let level: String      // green / yellow / red
    let desc: String
    let down: Int?
    let flat: Int?
    let total: Int?
}

// MARK: - 大跌预警响应
struct CrashWarningResponse: Codable {
    let timestamp: String
    let signals: [CrashSignal]
    let recommendation: String
    let confidence: Double
}

// MARK: - 低位突破股票
struct LowBreakStock: Codable, Identifiable, Hashable {
    let id = UUID()
    let code: String
    let name: String
    let price: Double
    let pct: Double
    let ma20: Double
    let distancePct: Double
    let signalScore: Double

    enum CodingKeys: String, CodingKey {
        case code, name, price, pct, ma20
        case distancePct = "distance_pct"
        case signalScore = "signal_score"
    }
}

// MARK: - 低位突破响应
struct LowBreakResponse: Codable {
    let timestamp: String
    let stocks: [LowBreakStock]
}

// MARK: - 带血筹码股票
struct BloodChipsStock: Codable, Identifiable, Hashable {
    let id = UUID()
    let code: String
    let name: String
    let price: Double
    let pct: Double
    let gapPct: Double
    let low60d: Double
    let distToLowPct: Double
    let type: String

    enum CodingKeys: String, CodingKey {
        case code, name, price, pct
        case gapPct = "gap_pct"
        case low60d = "low_60d"
        case distToLowPct = "dist_to_low_pct"
        case type
    }
}

// MARK: - 带血筹码响应
struct BloodChipsResponse: Codable {
    let timestamp: String
    let stocks: [BloodChipsStock]
    let scannedCount: Int?

    enum CodingKeys: String, CodingKey {
        case timestamp, stocks
        case scannedCount = "scanned_count"
    }
}

// MARK: - 健康检查
struct HealthResponse: Codable {
    let status: String
    let db: String
    let pythonVersion: String
    let uptimeSeconds: Double

    enum CodingKeys: String, CodingKey {
        case status, db
        case pythonVersion = "python_version"
        case uptimeSeconds = "uptime_seconds"
    }
}
