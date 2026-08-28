#!/usr/bin/env node
const { existsSync } = require('fs');
const { spawnSync } = require('child_process');
const { tmpdir } = require('os');
const path = require('path');

function parseArgs(argv) {
  const out = {
    projectName: '',
    branch: '',
    commitHash: '',
    dryRun: false,
    skipBuild: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const token = String(argv[i] || '').trim();
    if (token === '--dry-run') out.dryRun = true;
    if (token === '--skip-build') out.skipBuild = true;
    if (token === '--project-name' || token === '--project') {
      out.projectName = String(argv[i + 1] || '').trim();
      i += 1;
    }
    if (token === '--branch') {
      out.branch = String(argv[i + 1] || '').trim();
      i += 1;
    }
    if (token === '--commit-hash') {
      out.commitHash = String(argv[i + 1] || '').trim();
      i += 1;
    }
  }
  return out;
}

function run(command, args, options = {}) {
  const executable = process.platform === 'win32' && !path.extname(command)
    ? `${command}.cmd`
    : command;
  const result = spawnSync(executable, args, {
    stdio: 'inherit',
    shell: false,
    cwd: options.cwd || process.cwd(),
    env: options.env || process.env,
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const projectName = args.projectName || process.env.CLOUDFLARE_PAGES_PROJECT || '';
  const branch = args.branch || process.env.CLOUDFLARE_PAGES_BRANCH || '';
  const commitHash = args.commitHash || process.env.CLOUDFLARE_PAGES_COMMIT_HASH || '';
  const repoRoot = path.resolve(__dirname, '..');
  const pagesDist = path.join(repoRoot, 'pages-dist');

  if (!projectName) {
    console.error('Missing Cloudflare Pages project name.');
    console.error('Use --project-name <name> or set CLOUDFLARE_PAGES_PROJECT.');
    process.exit(2);
  }

  if (!args.skipBuild) {
    run('npm', ['run', 'build'], { cwd: repoRoot });
  }

  if (!existsSync(path.join(pagesDist, 'index.html'))) {
    console.error('pages-dist/index.html not found. Build output is missing.');
    process.exit(3);
  }
  if (!existsSync(path.join(pagesDist, 'hard-copy.html'))) {
    console.error('pages-dist/hard-copy.html not found. Hard-copy page was not emitted.');
    process.exit(4);
  }

  const deployArgs = ['pages', 'deploy', pagesDist, '--project-name', projectName];
  if (branch) deployArgs.push('--branch', branch);
  if (commitHash) deployArgs.push('--commit-hash', commitHash);

  if (args.dryRun) {
    console.log(`Dry run: ${process.execPath} ${path.join(repoRoot, 'node_modules', 'wrangler', 'bin', 'wrangler.js')} ${deployArgs.join(' ')}`);
    return;
  }

  // Run outside the repository so a stale .wrangler/deploy redirect cannot
  // override this explicit Pages deployment.
  run(process.execPath, [path.join(repoRoot, 'node_modules', 'wrangler', 'bin', 'wrangler.js'), ...deployArgs], { cwd: tmpdir() });
}

main();
