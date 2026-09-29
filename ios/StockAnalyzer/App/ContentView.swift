import SwiftUI

// MARK: - TabBar 根视图
struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: 行情看板
            MarketView()
                .tabItem {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                    Text("行情")
                }
                .tag(0)

            // Tab 2: 选股
            ScannerPlaceholderView()
                .tabItem {
                    Image(systemName: "target")
                    Text("选股")
                }
                .tag(1)

            // Tab 3: 持仓
            PortfolioPlaceholderView()
                .tabItem {
                    Image(systemName: "briefcase")
                    Text("持仓")
                }
                .tag(2)

            // Tab 4: 设置
            SettingsView()
                .tabItem {
                    Image(systemName: "gearshape")
                    Text("设置")
                }
                .tag(3)
        }
        .tint(.stockUp)
    }
}

// MARK: - 选股占位
struct ScannerPlaceholderView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Image(systemName: "target")
                    .font(.system(size: 56))
                    .foregroundStyle(.secondary)
                Text("选股工具开发中")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Text("大跌预警 / 低位突破 / 带血筹码")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.black)
            .navigationTitle("🎯 选股")
        }
    }
}

// MARK: - 持仓占位
struct PortfolioPlaceholderView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Image(systemName: "briefcase")
                    .font(.system(size: 56))
                    .foregroundStyle(.secondary)
                Text("持仓管理开发中")
                    .font(.title3)
                    .foregroundStyle(.secondary)
                Text("手动录入 + 实时盈亏计算")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color.black)
            .navigationTitle("💼 持仓")
        }
    }
}
