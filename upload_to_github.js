#!/usr/bin/env node
/**
 * 批量上传文件到 GitHub 仓库 onebody/homework
 * 通过调用 mcp__github__create_or_update_file 工具
 */

const fs = require('fs');
const path = require('path');

const OWNER = 'onebody';
const REPO = 'homework';
const BRANCH = 'main';

// 要上传的项目目录
const PROJECTS = [
  { localDir: 'points-system', remotePrefix: 'points-system' },
  { localDir: 'summer-homework-checkin', remotePrefix: 'summer-homework-checkin' },
];

// 排除模式
const EXCLUDE_PATTERNS = [
  /\.git\//,
  /__pycache__/,
  /\.pyc$/,
  /\.db$/,
  /\.db-wal$/,
  /\.db-shm$/,
  /uploads\//,
  /\.DS_Store/,
  /node_modules/,
];

function shouldExclude(filePath) {
  return EXCLUDE_PATTERNS.some(pattern => pattern.test(filePath));
}

function collectFiles(baseDir, prefix) {
  const results = [];
  
  function walk(dir, relPath) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relativePath = path.join(relPath, entry.name);
      
      if (shouldExclude(relativePath)) continue;
      
      if (entry.isDirectory()) {
        walk(fullPath, relativePath);
      } else if (entry.isFile()) {
        results.push({
          localPath: fullPath,
          remotePath: prefix ? `${prefix}/${relativePath}` : relativePath,
        });
      }
    }
  }
  
  walk(baseDir, '');
  return results;
}

// 收集所有文件
const allFiles = [];
for (const project of PROJECTS) {
  const localDir = path.join('/Users/fcj/workspace/hanghang_WS', project.localDir);
  if (!fs.existsSync(localDir)) {
    console.error(`目录不存在: ${localDir}`);
    continue;
  }
  const files = collectFiles(localDir, project.remotePrefix);
  allFiles.push(...files);
  console.log(`收集 ${project.localDir}: ${files.length} 个文件`);
}

console.log(`\n总计 ${allFiles.length} 个文件待上传\n`);

// 输出文件清单
for (const f of allFiles) {
  console.log(f.remotePath);
}

// 将文件列表写入 JSON 供后续使用
fs.writeFileSync('/tmp/upload_files.json', JSON.stringify(allFiles, null, 2));
console.log(`\n文件列表已保存到 /tmp/upload_files.json`);
