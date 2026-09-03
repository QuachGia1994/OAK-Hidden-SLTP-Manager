import Foundation
import Security

enum OAKAPIError: LocalizedError, Sendable {
    case invalidURL
    case unauthorized
    case server(Int, String)
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .invalidURL: "Invalid OAK API URL"
        case .unauthorized: "Dashboard API key is invalid or expired"
        case let .server(code, message): "OAK API \(code): \(message)"
        case .invalidResponse: "OAK API returned an invalid response"
        }
    }
}

struct OAKAPIClient: Sendable {
    let baseURL: URL

    init(baseURL: URL = URL(string: "https://www.oakgatekeeper.uk")!) {
        self.baseURL = baseURL
    }

    func fetchApp(apiKey: String) async throws -> MobileAppPayload {
        try await request(path: "/api/mobile/app", apiKey: apiKey)
    }

    func fetchAccounts(apiKey: String) async throws -> AccountPayload {
        try await request(path: "/api/accounts", apiKey: apiKey)
    }

    func setAccountEnabled(apiKey: String, id: String, enabled: Bool) async throws -> AccountPayload {
        struct Body: Encodable, Sendable { let id: String; let enabled: Bool }
        struct Envelope: Decodable, Sendable { let ok: Bool; let payload: AccountPayload }
        let body = try JSONEncoder().encode(Body(id: id, enabled: enabled))
        let envelope: Envelope = try await request(path: "/api/accounts", apiKey: apiKey, method: "PATCH", body: body)
        return envelope.payload
    }

    private func request<T: Decodable & Sendable>(
        path: String,
        apiKey: String,
        method: String = "GET",
        body: Data? = nil
    ) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else { throw OAKAPIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.httpBody = body
        request.timeoutInterval = 20
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw OAKAPIError.invalidResponse }
        if http.statusCode == 401 || http.statusCode == 403 { throw OAKAPIError.unauthorized }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw OAKAPIError.server(http.statusCode, message ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode))
        }
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw OAKAPIError.invalidResponse
        }
    }
}

enum KeychainStore {
    private static let service = "uk.oakgatekeeper.mobile"
    private static let account = "oak.dashboard.api-key"

    static func readAPIKey() -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let value = String(data: data, encoding: .utf8)
        else { return "" }
        return value
    }

    static func writeAPIKey(_ value: String) throws {
        try deleteAPIKey()
        guard !value.isEmpty, let data = value.data(using: .utf8) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            kSecValueData as String: data,
        ]
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else { throw OAKAPIError.server(Int(status), "Unable to store API key") }
    }

    static func deleteAPIKey() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw OAKAPIError.server(Int(status), "Unable to clear API key")
        }
    }
}
