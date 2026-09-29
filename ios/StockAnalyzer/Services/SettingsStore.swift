import Foundation
import SwiftUI

// MARK: - API 配置
@MainActor
final class SettingsStore: ObservableObject {
    @Published var apiBaseURL: String {
        didSet { UserDefaults.standard.set(apiBaseURL, forKey: "apiBaseURL") }
    }
    @Published var refreshInterval: Int { // 秒
        didSet { UserDefaults.standard.set(refreshInterval, forKey: "refreshInterval") }
    }

    static let shared = SettingsStore()

    // 默认值 —— 用户需要改成自己 Mac mini 的局域网 IP
    private static let defaultBaseURL = "http://192.168.3.60:5001"  // macOS 5000 被 AirPlay 占用，默认用 5001

    private init() {
        let defaults = UserDefaults.standard
        let saved = defaults.string(forKey: "apiBaseURL") ?? Self.defaultBaseURL
        self.apiBaseURL = saved
        self.refreshInterval = defaults.object(forKey: "refreshInterval") as? Int ?? 30
    }

    // MARK: - URL 构造
    var baseURL: URL? {
        URL(string: apiBaseURL.trimmingCharacters(in: CharacterSet.whitespacesAndNewlines))
    }

    func endpoint(_ path: String) -> URL? {
        baseURL?.appendingPathComponent(path)
    }

    // MARK: - 连接测试
    func testConnection() async throws -> HealthResponse {
        guard let url = endpoint("api/v1/health") else {
            throw APIError.invalidURL
        }
        return try await APIService.shared.get(url)
    }
}
