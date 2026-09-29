import SwiftUI

// MARK: - 指数卡片
struct IndexCardView: View {
    let index: RealtimeIndex
    let isLoading: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 名称
            Text(index.name)
                .font(.system(.subheadline, design: .rounded, weight: .medium))
                .foregroundStyle(.secondary)

            // 当前价
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(index.displayPrice)
                    .font(.system(size: 28, weight: .bold, design: .monospaced))
                    .foregroundStyle(priceColor)
                Text(index.displayPct)
                    .font(.system(size: 16, weight: .semibold, design: .monospaced))
                    .foregroundStyle(priceColor)
            }

            // 今高/今低
            HStack(spacing: 16) {
                if let high = index.high, let low = index.low {
                    HStack(spacing: 4) {
                        Text("高")
                            .font(.system(size: 11))
                            .foregroundStyle(.tertiary)
                        Text(String(format: "%.2f", high))
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(Color.stockUp)
                    }
                    HStack(spacing: 4) {
                        Text("低")
                            .font(.system(size: 11))
                            .foregroundStyle(.tertiary)
                        Text(String(format: "%.2f", low))
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(Color.stockDown)
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(borderColor, lineWidth: 1)
        )
        .overlay(alignment: .topTrailing) {
            if isLoading {
                ProgressView()
                    .progressViewStyle(.circular)
                    .controlSize(.small)
                    .tint(.secondary)
                    .padding(12)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: index.price)
    }

    private var priceColor: Color {
        if index.isUp { return .stockUp }
        if index.isDown { return .stockDown }
        return .stockFlat
    }

    private var borderColor: Color {
        priceColor.opacity(0.3)
    }
}
