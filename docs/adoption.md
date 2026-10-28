# Adopting CueLABS™ Engineering Standards

## Choose an installation scope

### User scope

Use user scope when one developer wants the skills available across projects:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all --agent codex --scope user
```

Run the same command with `--agent cursor` for Cursor.

### Project scope

Use project scope when a repository should carry a reviewed, reproducible skill
set:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all --agent codex --scope project --pin v2.5.0
```

Review and commit the resulting `.agents/skills/` tree. Update it deliberately
through a pull request.

### Selective adoption

External projects can install a single focused skill and use the portable
`base` profile:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  cuelabs-engineering-standards --agent cursor --scope project
gh skill install cuesoftinc/oss-engineering-standards \
  cuelabs-web-standard --agent cursor --scope project
```

## Add the project manifest

The manifest belongs to adopter repositories. This catalog repository is the
canon source, not an adopter, it carries no `.cuelabs/project.yaml`, and its
repository files (a documentation-repo `.gitignore`, catalog-specific
contributing and PR-template content) are intentionally not template-identical.

Copy the example:

```bash
mkdir -p .cuelabs
cp .agents/skills/cuelabs-engineering-standards/assets/project.example.yaml \
  .cuelabs/project.yaml
```

Record only current, approved state:

- `active`: implemented and maintained;
- `planned`: approved future work, not build-ready;
- `paused`: intentionally not progressing;
- `absent`: deliberately out of scope.

Do not mark a backend or mobile app active merely because the standard supports
one. Follow the engineering skill's
[project manifest syntax](../skills/cuelabs-engineering-standards/references/project-manifest.md);
unsupported YAML features fail explicitly so editor and CI behavior stays
portable.

## Adoption sequence

1. Run an audit and save the report.
2. Review the project manifest with the product owner.
3. Apply missing portable baseline files.
4. Resolve deviations in small, reviewable pull requests.
5. Activate focused skills only for implemented surfaces.
6. Pin a released standards version.
7. Update through normal dependency-governance pull requests.

Existing projects should follow the [v2 migration guide](migrations/v2.md).
