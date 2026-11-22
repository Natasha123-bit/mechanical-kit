// 逐页打印文本层：./dumptext <pdf> <from> <to>   （1 起，含首含尾）
// 编译：swiftc -O dumptext.swift -o dumptext
// 用途：扫描件文本层是 CID 乱码，但页眉的印刷页码 / 图表号仍可读，
//       拿它定章边界与偏移，比 chmap(6 分钟) 和读页图都快且不漏。
import Foundation
import PDFKit

let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let from = Int(a[2])!, to = Int(a[3])!
for n in from...to {
    guard let p = doc.page(at: n - 1), let s = p.string else { print("p\(n): <none>"); continue }
    let flat = s.replacingOccurrences(of: "\n", with: " \u{23CE} ")
    print("=== p\(n) [\(s.count)] \(flat.prefix(300))")
}