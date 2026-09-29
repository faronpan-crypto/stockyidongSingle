import SwiftUI

// MARK: - 设置页
struct SettingsView: View {
    @EnvironmentObject var settings: SettingsStore

    @State private var apiURLInput: String = ""
    @State private var testing = false
    @State private var testResult: String?
    @State private var testSuccess: Bool = false

    private let refreshOptions = [10, 30, 60, 120]

    var body: some View {
        NavigationStack {
            Form {
                // MARK: API 服务器
                Section("API 服务器") {
                    HStack {
                        Image(systemName: "server.rack")
                            .foregroundStyle(Color.accentBlue)
                        TextField("http://192.168.x.x:5001", text: $apiURLInput)
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                            .autocorrectionDisabled()
                    }

                    HStack {
                        Button {
                            saveAndTest()
                        } label: {
                            HStack {
                                if testing {
                                    ProgressView().controlSize(.small)
                                } else {
                                    Image(systemName: "bolt.circle")
                                }
                                Text("测试连接")
                            }
                        }
                        .disabled(testing || apiURLInput.isEmpty)

                        Spacer()

                        if let result = testResult {
                            HStack(spacing: 4) {
                                Image(systemName: testSuccess ? "checkmark.circle.fill" : "xmark.circle.fill")
                                    .foregroundStyle(testSuccess ? Color.stockUp : Color.stockDown)
                                Text(result)
                                    .font(.caption)
                                    .foregroundStyle(testSuccess ? Color.stockUp : Color.stockDown)
                            }
                        }
                    }

                    // 当前服务器状态
                    if let health = healthCache {
                        LabeledContent("状态", value: health.status == "ok" ? "✅ 在线" : "❌ 离线")
                        LabeledContent("数据库", value: health.db)
                        LabeledContent("运行时间", value: "\(Int(health.uptimeSeconds))s")
                    }
                }

                // MARK: 自动刷新
                Section("自动刷新频率") {
                    Picker("刷新间隔", selection: $settings.refreshInterval) {
                        ForEach(refreshOptions, id: \.self) { sec in
                            Text("\(sec) 秒")
                                .tag(sec)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                // MARK: 关于
                Section("关于") {
                    LabeledContent("版本", value: "1.0.0")
                    LabeledContent("最低 iOS", value: "16.0")
                    LabeledContent("Bundle ID", value: "com.stockidong.analyzer")
                    Link("项目源码", destination: URL(string: "https://github.com")!)
                }

                // MARK: 使用说明
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("📱 快速开始")
                            .font(.headline)
                        Text("""
                        1. 在 Mac mini 上启动 Python API 服务器：
                           cd src && python3 api_server.py
                        2. 查看 Mac 的局域网 IP（系统设置 → 网络）
                        3. 在上方输入框填入 http://IP:5001
                        4. 点击"测试连接"，成功后自动生效
                        """)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("使用说明")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.black)
            .navigationTitle("⚙️ 设置")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                apiURLInput = settings.apiBaseURL
                Task { await loadHealthCache() }
            }
        }
    }

    @State private var healthCache: HealthResponse?

    private func saveAndTest() {
        settings.apiBaseURL = apiURLInput.trimmingCharacters(in: .whitespacesAndNewlines)
        testResult = nil
        testSuccess = false
        testing = true
        Task {
            do {
                let health = try await settings.testConnection()
                await MainActor.run {
                    self.healthCache = health
                    self.testResult = "连接成功"
                    self.testSuccess = true
                    self.testing = false
                }
            } catch {
                await MainActor.run {
                    self.testResult = error.localizedDescription
                    self.testSuccess = false
                    self.testing = false
                }
            }
        }
    }

    private func loadHealthCache() async {
        do {
            healthCache = try await settings.testConnection()
        } catch {
            healthCache = nil
        }
    }
}
