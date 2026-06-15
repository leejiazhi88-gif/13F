const fs = require("fs");

const html = fs.readFileSync("investors.html", "utf8");
const scripts = [...html.matchAll(/<script(?:\s+src="[^"]+")?>([\s\S]*?)<\/script>/g)]
  .map(match => match[1])
  .filter(Boolean);

for (const code of scripts) {
  new Function(code);
}

console.log(JSON.stringify({ inlineScripts: scripts.length, syntax: "ok" }));
