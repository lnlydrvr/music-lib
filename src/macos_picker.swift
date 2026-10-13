// Нативный выбор папки/файла через NSOpenPanel.
//
// Локализацию подключает Python-обёртка: пустой `<lang>.lproj` рядом
// с бинарём (в каталоге кеша) регистрирует системный язык, и кнопки панели
// говорят по-русски/на языке системы. Без него `Bundle.main.preferredLocalizations`
// у голого бинаря всегда `["en"]` — диалог `osascript choose folder` к этому же
// показывает английский фолбэк даже на русской системе.
//
// Процесс — CLI без бандла, поэтому панель инициализируем как часть
// NSApplication: `setActivationPolicy(.accessory)` + `NSApp.run()` с
// `panel.begin(...)` и активацией поверх других окон. Без этого диалог
// открывается позади окна браузера и пропадает при фокусе.

import AppKit
import Foundation

var kind = "folder"
var start: String?

let argv = CommandLine.arguments
var idx = 1
while idx < argv.count {
    switch argv[idx] {
    case "--kind":
        idx += 1
        if idx < argv.count { kind = argv[idx] }
    case "--start":
        idx += 1
        if idx < argv.count { start = argv[idx] }
    default:
        break
    }
    idx += 1
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
app.finishLaunching()

let panel = NSOpenPanel()
panel.allowsMultipleSelection = false
panel.canCreateDirectories = true
if kind == "file" {
    panel.canChooseDirectories = false
    panel.canChooseFiles = true
} else {
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
}
if let raw = start, !raw.isEmpty, FileManager.default.fileExists(atPath: raw) {
    panel.directoryURL = URL(fileURLWithPath: raw, isDirectory: true)
}

panel.begin { response in
    var chosen = ""
    if response == .OK, let url = panel.url,
       FileManager.default.fileExists(atPath: url.path) {
        chosen = url.path
    }
    print(chosen)
    exit(0)
}
app.activate(ignoringOtherApps: true)
app.run()