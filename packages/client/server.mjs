import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { pythonTransport } from "./node.mjs";

const root = fileURLToPath(new URL(".", import.meta.url));
/** Hosts can embed the client instead; this server is the standalone workbench. */
export function createWorkbench({
  space,
  python = "python",
  pythonPath = resolve(root, "../../src"),
} = {}) {
  const transport = pythonTransport({ python, pythonPath });
  const assets = new Map([
    ["/", "workbench.html"],
    ...["client", "picker", "workbench"].map((n) => [
      "/lib/" + n + ".js",
      "lib/" + n + ".js",
    ]),
  ]);
  return createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, "http://localhost").pathname;
      if (req.method === "POST" && pathname === "/api") {
        let body = "";
        for await (const chunk of req) {
          body += chunk;
          if (body.length > 8 * 1024 * 1024)
            throw new Error("Request exceeds 8 MB");
        }
        const request = JSON.parse(body);
        if (space) request.space = space;
        const pathFields = {
          project: ["path"],
          run: ["output", "base"],
          manuscript: ["output", "base"],
          export: ["output"],
        };
        for (const key of pathFields[request.action] || []) {
          if (request[key] !== undefined)
            request[key] = resolve(space || process.cwd(), request[key]);
        }
        res.writeHead(200, {
          "Content-Type": "application/x-ndjson; charset=utf-8",
          "Cache-Control": "no-store",
        });
        try {
          const value = await transport(request, (event) =>
            res.write(
              JSON.stringify({ type: "progress", value: event }) + "\n",
            ),
          );
          res.end(JSON.stringify({ type: "result", value }) + "\n");
        } catch (error) {
          res.end(
            JSON.stringify({ type: "error", message: error.message }) + "\n",
          );
        }
      } else if (req.method === "GET" && assets.has(pathname)) {
        const asset = assets.get(pathname);
        const body = await readFile(resolve(root, asset));
        res.writeHead(200, {
          "Content-Type": asset.endsWith(".html")
            ? "text/html; charset=utf-8"
            : "text/javascript; charset=utf-8",
        });
        res.end(body);
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    } catch (error) {
      if (!res.headersSent)
        res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(error.message);
    }
  });
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const args = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    if (!process.argv[i].startsWith("--") || !process.argv[i + 1])
      throw new Error("Use --space PATH --python EXECUTABLE --port NUMBER");
    args[process.argv[i].slice(2)] = process.argv[i + 1];
  }
  const server = createWorkbench({
    space: args.space,
    python: args.python,
    pythonPath: args["python-path"],
  });
  server.listen(Number(args.port || 8787), "127.0.0.1", () =>
    console.log("HSS workbench: http://127.0.0.1:" + server.address().port),
  );
}
