import SwiftUI

// MARK: - 价格/涨跌幅标签（红涨绿跌）
struct PriceLabel: View {
    let price: String
    let pct: String?
    var showArrow: Bool = true

    private var isUp: Bool {
        guard let p = pct else { return false }
        return p.hasPrefix("+")
    }
    private var isDown: Bool {
        guard let p = pct else { return false }
        return p.hasPrefix("-")
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(price)
                .font(.system(.body, design: .monospaced))
            if let pct = pct {
                if showArrow {
                    Image(systemName: isUp ? "arrowtriangle.up.fill" : (isDown ? "arrowtriangle.down.fill" : "minus"))
                        .font(.system(size: 8))
                }
                Text(pct)
                    .font(.system(.caption, design: .monospaced))
            }
        }
        .foregroundStyle(color)
    }

    private var color: Color {
        if isUp { return .stockUp }
        if isDown { return .stockDown }
        return .stockFlat
    }
}

// MARK: - 加载中
struct LoadingView: View {
    var message: String = "加载中..."
    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .stockUp))
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - 错误重试
struct ErrorRetryView: View {
    let error: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(.orange)
            Text(error)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button(action: onRetry) {
                Label("重试", systemImage: "arrow.clockwise")
                    .font(.headline)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color.accentColor)
                    .foregroundStyle(.white)
                    .clipShape(Capsule())
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
