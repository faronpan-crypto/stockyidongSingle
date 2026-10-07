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

    // 默认值 —— 模拟器用 localhost，真机改成自己 Mac 的局域网 IP
    private static let defaultBaseURL = "http://127.0.0.1:5001"

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
