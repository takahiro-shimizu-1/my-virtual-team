#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const AGENTS_DIR = path.join(ROOT, 'agents');
const REGISTRY_DIR = path.join(ROOT, 'registry');
const GENERATED_SKILLS_DIR = path.join(ROOT, '.claude', 'skills', 'generated');
const AGENTS_COMPAT_FILE = path.join(ROOT, 'AGENTS_CLAUDE.md');
const GITNEXUS_KNOWLEDGE_DIR = path.join(ROOT, '.gitnexus', 'knowledge');
const BYTES_PER_TOKEN = 3.7;
const JA_PARTICLES = new Set(['を', 'は', 'が', 'の', 'で', 'に', 'へ', 'と', 'も', 'か']);

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function ensureSymlink(linkPath, targetPath) {
  ensureDir(path.dirname(linkPath));
  const relativeTarget = path.relative(path.dirname(linkPath), targetPath);
  try {
    const existing = fs.readlinkSync(linkPath);
    if (existing === relativeTarget) return;
    fs.unlinkSync(linkPath);
  } catch (error) {
    if (fs.existsSync(linkPath)) {
      fs.rmSync(linkPath, { recursive: true, force: true });
    }
  }
  fs.symlinkSync(relativeTarget, linkPath);
}

function mirrorMarkdownDir(sourceDir, targetDir) {
  if (!fs.existsSync(sourceDir)) return;
  const entries = fs.readdirSync(sourceDir, { withFileTypes: true });
  ensureDir(targetDir);

  for (const entry of entries) {
    const sourcePath = path.join(sourceDir, entry.name);
    const targetPath = path.join(targetDir, entry.name);

    if (entry.isDirectory()) {
      mirrorMarkdownDir(sourcePath, targetPath);
      continue;
    }

    if (entry.isFile() && entry.name.endsWith('.md')) {
      ensureSymlink(targetPath, sourcePath);
    }
  }
}

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(full));
    } else if (entry.isFile() && entry.name.endsWith('.md')) {
      files.push(full);
    }
  }
  return files;
}

function parseArray(raw) {
  const inner = raw.trim().replace(/^\[/, '').replace(/\]$/, '');
  if (!inner.trim()) return [];
  return inner
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)
    .map((v) => v.replace(/^['"]|['"]$/g, ''));
}

function parseValue(raw) {
  const value = raw.trim();
  if (value.startsWith('[') && value.endsWith(']')) return parseArray(value);
  if (/^\d+$/.test(value)) return Number(value);
  return value.replace(/^['"]|['"]$/g, '');
}

function parseFrontmatter(text) {
  const match = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) return null;

  const result = {};
  let currentObject = null;

  for (const line of match[1].split('\n')) {
    if (!line.trim()) continue;

    let rootMatch = line.match(/^([a-z_]+):\s*(.*)$/);
    if (rootMatch) {
      const [, key, raw] = rootMatch;
      if (!raw.trim()) {
        result[key] = {};
        currentObject = key;
      } else {
        result[key] = parseValue(raw);
        currentObject = null;
      }
      continue;
    }

    const listMatch = line.match(/^  -\s*(.*)$/);
    if (listMatch && currentObject) {
      const [, raw] = listMatch;
      if (!Array.isArray(result[currentObject])) {
        result[currentObject] = [];
      }
      result[currentObject].push(parseValue(raw));
      continue;
    }

    const nestedMatch = line.match(/^  ([a-z_]+):\s*(.*)$/);
    if (nestedMatch && currentObject) {
      const [, key, raw] = nestedMatch;
      if (Array.isArray(result[currentObject])) {
        result[currentObject] = {};
      }
      result[currentObject][key] = parseValue(raw);
    }
  }

  return result;
}

function estimateTokens(filePath) {
  const stat = fs.statSync(filePath);
  return Math.ceil(stat.size / BYTES_PER_TOKEN);
}

function slugFromPath(filePath) {
  return path.basename(filePath, '.md');
}

function extractName(text) {
  const line = text.split('\n').find((v) => v.startsWith('# '));
  return line ? line.replace(/^# /, '').trim() : '';
}

function extractDepartmentName(text) {
  const match = text.match(/## 所属\n([^\n]+)/);
  return match ? match[1].trim() : '';
}

function extractSection(text, title) {
  const pattern = new RegExp(`## ${title}\\n([\\s\\S]*?)(\\n## |$)`);
  const match = text.match(pattern);
  return match ? match[1].trim() : '';
}

function normalizeAgentName(name) {
  return name.replace(/\s*（.*?）$/, '').trim();
}

function escapeQuoted(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

function unique(values) {
  const seen = new Set();
  const result = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

function expandSearchTerms(text) {
  const terms = [];
  const normalized = String(text)
    .replace(/[()（）［］【】「」『』、。,:;!?]/g, ' ')
    .replace(/\//g, ' ')
    .trim();

  if (!normalized) return terms;

  for (const part of normalized.split(/\s+/)) {
    if (!part) continue;
    terms.push(part);

    const asciiParts = part
      .replace(/(?<=[A-Za-z0-9])-(?=[A-Za-z0-9])/g, ' ')
      .split(/\s+/)
      .filter(Boolean);
    terms.push(...asciiParts);

    const cjkChunks = part.match(/[\u3000-\u9fff\uf900-\ufaff]+/g) || [];
    for (const chunk of cjkChunks) {
      const cleaned = Array.from(chunk)
        .filter((char) => !JA_PARTICLES.has(char))
        .join('');
      if (!cleaned) continue;
      terms.push(cleaned);
      if (cleaned.length === 1) continue;
      for (let i = 0; i < cleaned.length - 1; i += 1) {
        terms.push(cleaned.slice(i, i + 2));
      }
    }
  }

  return unique(terms);
}

function buildSearchKeywords(parts) {
  const raw = [];
  for (const part of parts) {
    if (!part) continue;
    raw.push(String(part).trim());
    raw.push(...expandSearchTerms(part));
  }
  return unique(raw);
}

function buildAgentsClaude(agents) {
  const lines = [
    '# AGENTS_CLAUDE.md',
    '',
    '<!-- generated by npm run registry:build; do not edit manually -->',
    '',
    'generated_agents:',
  ];

  for (const agent of agents) {
    lines.push(`  - agent_id: "${escapeQuoted(agent.agent_id)}"`);
    lines.push(`    name: "${escapeQuoted(agent.name)}"`);
    lines.push(`    role: "${escapeQuoted(agent.role)}"`);
    lines.push(`    society: "${escapeQuoted(agent.department)}"`);
    lines.push(`    type: "${escapeQuoted(agent.type)}"`);
    lines.push('    keywords:');
    for (const keyword of agent.keywords) {
      lines.push(`      - "${escapeQuoted(keyword)}"`);
    }
    lines.push('');
  }

  return lines.join('\n').trimEnd() + '\n';
}

function build() {
  ensureDir(REGISTRY_DIR);
  fs.rmSync(GITNEXUS_KNOWLEDGE_DIR, { recursive: true, force: true });
  ensureDir(GITNEXUS_KNOWLEDGE_DIR);

  const agentFiles = walk(AGENTS_DIR);
  const agents = [];
  const agentCompat = [];
  const guidelineMap = {};
  const agentPolicies = {};
  const generatedSkills = [];

  for (const fullPath of agentFiles) {
    const text = fs.readFileSync(fullPath, 'utf8');
    const frontmatter = parseFrontmatter(text);
    if (!frontmatter) {
      throw new Error(`Frontmatter not found: ${path.relative(ROOT, fullPath)}`);
    }

    const relativePath = path.relative(ROOT, fullPath).replace(/\\/g, '/');
    const name = extractName(text);
    const departmentName = extractDepartmentName(text);
    const role = extractSection(text, '役割').replace(/\s+/g, ' ').trim();

    const agent = {
      agent_id: frontmatter.agent_id,
      name,
      department: frontmatter.department,
      department_name: departmentName,
      file: relativePath,
      keywords: frontmatter.keywords || [],
      context_budget: frontmatter.context_budget || 0,
      approval_policy: frontmatter.approval_policy || '',
      execution_mode: frontmatter.execution_mode || '',
    };
    agents.push(agent);
    agentCompat.push({
      agent_id: frontmatter.agent_id,
      name: normalizeAgentName(name),
      role,
      department: frontmatter.department,
      type: 'local',
      keywords: buildSearchKeywords([
        ...(frontmatter.keywords || []),
        role,
        departmentName,
      ]),
    });

    const contextRefs = frontmatter.context_refs || {};
    agentPolicies[frontmatter.agent_id] = {
      always: [],
      on_demand: [],
      never: [],
    };

    for (const tier of ['always', 'on_demand', 'never']) {
      const paths = contextRefs[tier] || [];
      for (const refPath of paths) {
        const slug = slugFromPath(refPath);
        agentPolicies[frontmatter.agent_id][tier].push(slug);

        const absoluteRef = path.join(ROOT, refPath);
        if (!guidelineMap[slug] && fs.existsSync(absoluteRef)) {
          guidelineMap[slug] = {
            path: refPath,
            tokens: estimateTokens(absoluteRef),
          };
        }
      }
    }
  }

  agents.sort((a, b) => a.agent_id.localeCompare(b.agent_id));

  const meta = {
    version: '1.0',
    generated_at: new Date().toISOString(),
  };

  fs.writeFileSync(
    path.join(REGISTRY_DIR, 'agents.generated.json'),
    JSON.stringify({ ...meta, agents }, null, 2) + '\n'
  );

  fs.writeFileSync(
    path.join(REGISTRY_DIR, 'context-policy.generated.json'),
    JSON.stringify(
      {
        ...meta,
        guidelines: guidelineMap,
        agents: agentPolicies,
      },
      null,
      2
    ) + '\n'
  );

  if (fs.existsSync(GENERATED_SKILLS_DIR)) {
    const skillFiles = walk(GENERATED_SKILLS_DIR);
    for (const fullPath of skillFiles) {
      const text = fs.readFileSync(fullPath, 'utf8');
      const frontmatter = parseFrontmatter(text);
      if (!frontmatter) continue;
      generatedSkills.push({
        name: frontmatter.name || slugFromPath(fullPath),
        description: frontmatter.description || '',
        category: frontmatter.category || '',
        file: path.relative(ROOT, fullPath).replace(/\\/g, '/'),
        keywords: frontmatter.keywords || [],
        agents: frontmatter.agents || [],
        depends_on: frontmatter.depends_on || [],
      });
    }
  }

  generatedSkills.sort((a, b) => a.name.localeCompare(b.name));
  fs.writeFileSync(
    path.join(REGISTRY_DIR, 'skills.generated.json'),
    JSON.stringify({ ...meta, skills: generatedSkills }, null, 2) + '\n'
  );

  agentCompat.sort((a, b) => a.agent_id.localeCompare(b.agent_id));
  fs.writeFileSync(AGENTS_COMPAT_FILE, buildAgentsClaude(agentCompat));
  ensureSymlink(
    path.join(GITNEXUS_KNOWLEDGE_DIR, 'AGENTS_CLAUDE.md'),
    AGENTS_COMPAT_FILE
  );
  ensureSymlink(
    path.join(GITNEXUS_KNOWLEDGE_DIR, 'CLAUDE.md'),
    path.join(ROOT, 'CLAUDE.md')
  );
  ensureSymlink(
    path.join(GITNEXUS_KNOWLEDGE_DIR, 'DESIGN_CONSTRAINTS.md'),
    path.join(ROOT, 'DESIGN_CONSTRAINTS.md')
  );
  mirrorMarkdownDir(path.join(ROOT, 'guidelines'), path.join(GITNEXUS_KNOWLEDGE_DIR, 'guidelines'));
  mirrorMarkdownDir(path.join(ROOT, 'docs'), path.join(GITNEXUS_KNOWLEDGE_DIR, 'docs'));
  mirrorMarkdownDir(path.join(ROOT, 'templates'), path.join(GITNEXUS_KNOWLEDGE_DIR, 'templates'));
  mirrorMarkdownDir(path.join(ROOT, '.claude', 'rules'), path.join(GITNEXUS_KNOWLEDGE_DIR, 'rules'));

  console.log(
    `Generated registry, AGENTS_CLAUDE, and GitNexus knowledge mirror for ${agents.length} agents and ${generatedSkills.length} skills.`
  );
}

build();
