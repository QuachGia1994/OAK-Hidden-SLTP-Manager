using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

internal static class NeoTechC5Setup
{
    private const string EaName = "OAK_NeoTech_Compliance_EA.ex5";
    private const string EaResource = "OAK_NeoTech_Compliance_EA.ex5";
    private const string ShaResource = "OAK_NeoTech_Compliance_EA.sha256.txt";

    [STAThread]
    private static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool dryRun = HasArg(args, "--dry-run");
        bool quiet = HasArg(args, "--quiet");
        try
        {
            byte[] eaBytes = ReadResource(EaResource);
            string expectedHash = ReadExpectedHash();
            string embeddedHash = Sha256Hex(eaBytes);
            if (!String.Equals(expectedHash, embeddedHash, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Embedded EA checksum does not match the release checksum.");

            List<string> dataFolders = FindMt5DataFolders();
            if (dataFolders.Count == 0)
                throw new InvalidOperationException("No MT5 Data Folder was found. Open MT5 once, then run Setup again.");

            int installed = 0;
            int current = 0;
            List<string> failures = new List<string>();
            List<string> terminals = new List<string>();

            foreach (string folder in dataFolders)
            {
                string terminal = ReadTerminalName(folder);
                terminals.Add(terminal);
                try
                {
                    string experts = Path.Combine(folder, "MQL5", "Experts");
                    string target = Path.Combine(experts, EaName);
                    if (File.Exists(target) && String.Equals(Sha256File(target), expectedHash, StringComparison.OrdinalIgnoreCase))
                    {
                        current++;
                        continue;
                    }

                    if (dryRun)
                    {
                        installed++;
                        continue;
                    }
                    Directory.CreateDirectory(experts);
                    string temp = target + ".tmp." + Guid.NewGuid().ToString("N");
                    File.WriteAllBytes(temp, eaBytes);
                    if (!String.Equals(Sha256File(temp), expectedHash, StringComparison.OrdinalIgnoreCase))
                    {
                        File.Delete(temp);
                        throw new InvalidOperationException("verification failed after writing the EA");
                    }
                    if (File.Exists(target)) File.Delete(target);
                    File.Move(temp, target);
                    installed++;
                }
                catch (Exception ex)
                {
                    failures.Add(terminal + ": " + ex.Message);
                }
            }

            StringBuilder message = new StringBuilder();
            message.AppendLine(dryRun ? "OAK NeoTech C5 Setup preview passed." : "OAK NeoTech C5 Setup complete.");
            message.AppendLine();
            message.AppendLine((dryRun ? "Would install/update: " : "Installed/updated: ") + installed);
            message.AppendLine("Already current: " + current);
            message.AppendLine("MT5 terminals found: " + dataFolders.Count);
            if (failures.Count > 0)
            {
                message.AppendLine();
                message.AppendLine("Could not update:");
                foreach (string failure in failures) message.AppendLine("- " + failure);
            }
            if (!dryRun)
            {
                message.AppendLine();
                message.AppendLine("Final step in MT5:");
                message.AppendLine("Navigator > Expert Advisors > Refresh");
                message.AppendLine("Attach OAK_NeoTech_Compliance_EA to one chart.");
                message.AppendLine();
                message.AppendLine("Local C5 popup works without Telegram.");
                message.AppendLine("Click C5 LOOK on the chart to review symbols used in the current session.");
            }

            if (!quiet)
                MessageBox.Show(message.ToString(), "OAK NeoTech C5", MessageBoxButtons.OK,
                    failures.Count == 0 ? MessageBoxIcon.Information : MessageBoxIcon.Warning);
            return failures.Count == 0 ? 0 : 2;
        }
        catch (Exception ex)
        {
            if (!quiet)
                MessageBox.Show("Setup did not complete:\r\n\r\n" + ex.Message,
                    "OAK NeoTech C5", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    private static bool HasArg(string[] args, string expected)
    {
        foreach (string arg in args)
            if (String.Equals(arg, expected, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    private static byte[] ReadResource(string name)
    {
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
        {
            if (stream == null) throw new InvalidOperationException("Missing embedded resource: " + name);
            using (MemoryStream memory = new MemoryStream())
            {
                stream.CopyTo(memory);
                return memory.ToArray();
            }
        }
    }

    private static string ReadExpectedHash()
    {
        string text = Encoding.ASCII.GetString(ReadResource(ShaResource));
        string[] parts = text.Trim().Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0 || parts[0].Length != 64) throw new InvalidOperationException("Invalid embedded SHA-256 release file.");
        return parts[0].ToUpperInvariant();
    }

    private static List<string> FindMt5DataFolders()
    {
        List<string> result = new List<string>();
        string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string root = Path.Combine(appData, "MetaQuotes", "Terminal");
        if (!Directory.Exists(root)) return result;
        foreach (string folder in Directory.GetDirectories(root))
        {
            if (String.Equals(Path.GetFileName(folder), "Common", StringComparison.OrdinalIgnoreCase)) continue;
            if (!File.Exists(Path.Combine(folder, "origin.txt"))) continue;
            if (!Directory.Exists(Path.Combine(folder, "MQL5"))) continue;
            result.Add(folder);
        }
        return result;
    }

    private static string ReadTerminalName(string folder)
    {
        try
        {
            string[] lines = File.ReadAllLines(Path.Combine(folder, "origin.txt"));
            if (lines.Length > 0 && !String.IsNullOrWhiteSpace(lines[0])) return lines[0].Trim();
        }
        catch { }
        return Path.GetFileName(folder);
    }

    private static string Sha256File(string path)
    {
        using (FileStream stream = File.OpenRead(path))
        using (SHA256 sha = SHA256.Create())
            return ToHex(sha.ComputeHash(stream));
    }

    private static string Sha256Hex(byte[] bytes)
    {
        using (SHA256 sha = SHA256.Create()) return ToHex(sha.ComputeHash(bytes));
    }

    private static string ToHex(byte[] bytes)
    {
        StringBuilder value = new StringBuilder(bytes.Length * 2);
        foreach (byte b in bytes) value.Append(b.ToString("x2"));
        return value.ToString();
    }
}
