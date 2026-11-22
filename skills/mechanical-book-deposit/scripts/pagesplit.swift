// 按显式页表拆章（bin/pdfsplit 只吃连续 start-end，这里支持任意页表）
// 编译：swiftc -O pagesplit.swift -o pagesplit
// 用法：./pagesplit <book.pdf> <map.json> <outdir>
// map： [{"ch":11,"name":"蜗杆传动","pages":"255-286,290"}]   （1 起、含首含尾）
// 输出：chNN-章名.pdf
import Foundation
import PDFKit

let a = CommandLine.arguments
guard let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else { print("cannot open book"); exit(1) }
let map = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: a[2]))) as! [[String: Any]]
let outdir = URL(fileURLWithPath: a[3])
try? FileManager.default.createDirectory(at: outdir, withIntermediateDirectories: true)
print("book pages: \(doc.pageCount)")
for item in map {
    let ch = item["ch"] as! Int
    let name = item["name"] as! String
    let spec = item["pages"] as! String
    var idx: [Int] = []
    for part in spec.split(separator: ",") {
        let t = part.trimmingCharacters(in: .whitespaces)
        if t.contains("-") {
            let b = t.split(separator: "-").map { Int($0)! }
            idx += Array(b[0]...b[1])
        } else if let v = Int(t) { idx.append(v) }
    }
    let out = PDFDocument()
    for n in idx {
        guard n >= 1, n <= doc.pageCount, let p = doc.page(at: n - 1) else { print("SKIP \(n)"); continue }
        out.insert(p, at: out.pageCount)
    }
    let fn = String(format: "ch%02d-%@.pdf", ch, name)
    out.write(to: outdir.appendingPathComponent(fn))
    print("wrote \(fn) pages=\(out.pageCount) from \(spec)")
}