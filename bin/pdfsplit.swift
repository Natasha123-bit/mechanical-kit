// 按 JSON 章节地图把整本书拆成单章 PDF
// 编译：swiftc -O pdfsplit.swift -o pdfsplit
// 用法：./pdfsplit <book.pdf> <map.json> <outdir>
// map.json 形如：[{"ch": 5, "name": "螺纹连接", "start": 78, "end": 104}, ...]（页码 1 起、含首含尾）
import Foundation
import PDFKit

let args = CommandLine.arguments
guard args.count >= 4 else { print("usage: pdfsplit <book.pdf> <map.json> <outdir>"); exit(1) }
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else { print("cannot open book"); exit(1) }
let mapData = try! Data(contentsOf: URL(fileURLWithPath: args[2]))
let map = try! JSONSerialization.jsonObject(with: mapData) as! [[String: Any]]
let outdir = URL(fileURLWithPath: args[3])
try? FileManager.default.createDirectory(at: outdir, withIntermediateDirectories: true)

print("book pages: \(doc.pageCount)")
for item in map {
    let ch = item["ch"] as! Int
    let name = item["name"] as? String ?? ""
    let start = (item["start"] as! Int) - 1
    let end = (item["end"] as! Int) - 1
    guard start >= 0, end < doc.pageCount, start <= end else {
        print("SKIP ch\(ch): range \(start+1)-\(end+1) out of bounds"); continue
    }
    let out = PDFDocument()
    for i in start...end {
        if let p = doc.page(at: i) { out.insert(p, at: out.pageCount) }
    }
    let fn = String(format: "ch%02d-%@.pdf", ch, name)
    let url = outdir.appendingPathComponent(fn)
    out.write(to: url)
    print("wrote \(fn) pages=\(out.pageCount)")
}
