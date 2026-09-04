import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct OAKShareItem: Identifiable {
    let id = UUID()
    let url: URL
}

@MainActor
struct OAKActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

@MainActor
enum OAKImageTransfer {
    private static let exportFolder = "OAKImageExports"
    private static let retentionSeconds: TimeInterval = 24 * 60 * 60

    static func copyPNG(_ image: UIImage) -> Bool {
        guard let data = image.pngData(), !data.isEmpty else { return false }
        UIPasteboard.general.setItems(
            [[UTType.png.identifier: data]],
            options: [
                .localOnly: false,
                .expirationDate: Date().addingTimeInterval(retentionSeconds),
            ]
        )
        return true
    }

    static func exportPNG(_ image: UIImage, filename: String) -> URL? {
        guard let data = image.pngData(), !data.isEmpty else { return nil }
        do {
            let directory = try exportDirectory()
            prune(directory: directory)
            let safeName = filename.replacingOccurrences(of: "/", with: "-")
            let url = directory.appendingPathComponent(safeName).appendingPathExtension("png")
            try data.write(to: url, options: .atomic)
            return url
        } catch {
            return nil
        }
    }

    private static func exportDirectory() throws -> URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let directory = base.appendingPathComponent(exportFolder, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    private static func prune(directory: URL) {
        let cutoff = Date().addingTimeInterval(-retentionSeconds)
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: [.contentModificationDateKey],
            options: [.skipsHiddenFiles]
        ) else { return }
        for file in files {
            let modified = (try? file.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            if modified < cutoff { try? FileManager.default.removeItem(at: file) }
        }
    }
}
