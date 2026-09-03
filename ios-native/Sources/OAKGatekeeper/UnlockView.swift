import SwiftUI

@MainActor
struct UnlockView: View {
    @Environment(AppState.self) private var state
    @State private var key = ""
    @State private var busy = false
    @FocusState private var focused: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Spacer(minLength: 54)
                OAKPageHeader(
                    eyebrow: "OAK / MOBILE",
                    title: "OAK Gatekeeper",
                    subtitle: state.text(
                        vn: "Ứng dụng native iOS cho ROBOT SLTP · dữ liệu H1 lấy trực tiếp từ backend.",
                        en: "Native iOS client for ROBOT SLTP · H1 data comes directly from the backend."
                    )
                )

                OAKCard(tint: OAKColor.accent) {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                OAKEyebrow(text: "SECURE ACCESS")
                                Text(state.text(vn: "Mở khóa dashboard", en: "Unlock dashboard"))
                                    .font(.title2.bold())
                                    .foregroundStyle(OAKColor.text)
                            }
                            Spacer()
                            Image(systemName: "lock.shield.fill")
                                .font(.title2)
                                .foregroundStyle(OAKColor.accent)
                        }

                        SecureField("Dashboard API key", text: $key)
                            .textContentType(.password)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                            .focused($focused)
                            .padding(14)
                            .background(OAKColor.raised, in: RoundedRectangle(cornerRadius: 13, style: .continuous))
                            .overlay {
                                RoundedRectangle(cornerRadius: 13, style: .continuous)
                                    .stroke(OAKColor.border, lineWidth: 1)
                            }

                        Button {
                            Task { await unlock() }
                        } label: {
                            HStack(spacing: 9) {
                                if busy { ProgressView().controlSize(.small) }
                                Image(systemName: "arrow.right.circle.fill")
                                Text(state.text(vn: "MỞ KHÓA", en: "UNLOCK"))
                                    .font(.system(size: 13, weight: .black, design: .monospaced))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 13)
                        }
                        .buttonStyle(.glassProminent)
                        .tint(OAKColor.accent)
                        .disabled(busy || key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                        if !state.errorMessage.isEmpty {
                            Text(state.errorMessage)
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(OAKColor.danger)
                        }

                        Text(state.text(
                            vn: "API key chỉ được lưu trong Keychain của thiết bị. Ứng dụng không nhúng khóa vào binary.",
                            en: "The API key is stored only in this device's Keychain and is never embedded in the binary."
                        ))
                        .font(.footnote)
                        .foregroundStyle(OAKColor.muted)
                    }
                }
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(OAKColor.canvas)
        .onAppear { focused = true }
    }

    private func unlock() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do { try await state.unlock(candidate: key) } catch { state.errorMessage = error.localizedDescription }
    }
}
