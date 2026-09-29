import SwiftUI

// MARK: - Tab 1: 行情看板
struct MarketView: View {
    @EnvironmentObject var settings: SettingsStore

    @State private var indices: [RealtimeIndex] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var lastUpdated: Date?
    @State private var timer: Timer?
    @State private var showOfflineBadge = false

    // 指数映射（API key → UI id）
    private let indexKeys = ["sh000001", "sz399001", "sz399006"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // 顶部状态条
                    headerBar

                    // 三指数卡片
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 12),
                                        GridItem(.flexible(), spacing: 12)],
                              spacing: 12) {
                        ForEach(indices) { idx in
                            IndexCardView(index: idx, isLoading: isLoading)
                                .onTapGesture {
                                    // TODO: 跳详情页
                                }
                        }
                    }
                    .padding(.horizontal, 16)

                    // 底部时间戳
                    if let last = lastUpdated {
                        HStack {
                            Spacer()
                            Text("更新于 \(last.formatted(date: .omitted, time: .standard))")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }
                        .padding(.horizontal, 20)
                    }
                }
                .padding(.vertical, 12)
            }
            .background(Color.black.ignoresSafeArea())
            .navigationTitle("📊 行情")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await loadIndices(force: true) }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.system(size: 16, weight: .semibold))
                    }
                    .disabled(isLoading)
                }
            }
            .refreshable {
                await loadIndices(force: true)
            }
            .alert("加载失败", isPresented: .constant(errorMessage != nil), actions: {
                Button("重试") {
                    Task { await loadIndices(force: true) }
                }
                Button("取消", role: .cancel) { errorMessage = nil }
            }, message: {
                Text(errorMessage ?? "")
            })
        }
        .task {
            // 首次加载
            await loadIndices(force: true)
            // 启动自动刷新
            startAutoRefresh()
        }
        .onDisappear {
            stopAutoRefresh()
        }
        .onChange(of: settings.refreshInterval) { _ in
            restartAutoRefresh()
        }
    }

    // MARK: - 顶部状态条
    private var headerBar: some View {
        HStack {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .foregroundStyle(Color.stockUp)
            Text("A股三大指数")
                .font(.headline)
            Spacer()
            if showOfflineBadge {
                Label("离线", systemImage: "wifi.slash")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.orange.opacity(0.2))
                    .foregroundStyle(.orange)
                    .clipShape(Capsule())
            }
        }
        .padding(.horizontal, 20)
    }

    // MARK: - 数据加载
    private func loadIndices(force: Bool = false) async {
        guard let url = settings.endpoint("api/v1/indices") else {
            errorMessage = "API 地址无效，请在设置中检查"
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let raw = try await APIService.shared.rawGet(url)
            var loaded: [RealtimeIndex] = []
            for key in indexKeys {
                if let dict = raw[key] as? [String: Any] {
                    let idx = parseIndex(key: key, dict: dict)
                    loaded.append(idx)
                } else {
                    loaded.append(RealtimeIndex(
                        id: key, name: fallbackName(for: key),
                        price: nil, pct: nil, change: nil,
                        open: nil, high: nil, low: nil, prevClose: nil
                    ))
                }
            }
            await MainActor.run {
                self.indices = loaded
                self.lastUpdated = Date()
                self.showOfflineBadge = false
                self.errorMessage = nil
            }
        } catch {
            await MainActor.run {
                // 如果有缓存数据，只显示离线标签
                if !self.indices.isEmpty {
                    self.showOfflineBadge = true
                } else {
                    self.errorMessage = error.localizedDescription
                }
            }
        }
    }

    private func parseIndex(key: String, dict: [String: Any]) -> RealtimeIndex {
        let d = { (k: String) -> Double? in
            if let v = dict[k] as? NSNumber { return v.doubleValue }
            if let v = dict[k] as? Double { return v }
            return nil
        }
        return RealtimeIndex(
            id: key,
            name: dict["name"] as? String ?? fallbackName(for: key),
            price: d("price"),
            pct: d("pct"),
            change: d("change"),
            open: d("open"),
            high: d("high"),
            low: d("low"),
            prevClose: d("prev_close")
        )
    }

    private func fallbackName(for key: String) -> String {
        switch key {
        case "sh000001": return "上证指数"
        case "sz399001": return "深证成指"
        case "sz399006": return "创业板指"
        default: return key
        }
    }

    // MARK: - 自动刷新
    private func startAutoRefresh() {
        stopAutoRefresh()
        let interval = TimeInterval(max(settings.refreshInterval, 5))
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { _ in
            Task { await loadIndices() }
        }
    }

    private func stopAutoRefresh() {
        timer?.invalidate()
        timer = nil
    }

    private func restartAutoRefresh() {
        startAutoRefresh()
    }
}
