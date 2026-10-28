# Standards governance

## Audience

The project serves:

- CueLABS™ maintainers enforcing organization policy;
- product contributors implementing one repository;
- partners and external teams adopting the portable base;
- coding agents and CI systems consuming deterministic contracts.

## Ownership

CODEOWNERS approve changes. A change affecting a focused domain should include
review from a maintainer familiar with that domain. Product-specific decisions
remain owned by the product repository.

## Decision levels

1. **Base profile** — portable open-source safety and repository hygiene.
2. **CueLABS profile** — organization-wide technology and delivery policy.
3. **Product manifest** — current capabilities, surface readiness, deployment,
   and documented deviations.
4. **Product documentation** — detailed behavior and implementation contracts.

A higher level must not absorb state that belongs to a lower level.

## Change process

Clarifications can use a normal pull request. Additive, behavior, or breaking
changes must document:

- the problem and evidence;
- affected profiles and skills;
- affected repositories;
- migration and rollback;
- evaluation changes;
- compatibility impact;
- deprecation window when appropriate.

Breaking installation, schema, or behavioral changes require a major release.
Additive backward-compatible capabilities require a minor release. Corrections
and clarifications require a patch release.

## Exceptions

Record intentional deviations in `.cuelabs/project.yaml` with a stable ID,
reason, and optional expiry. Do not encode one product's exception as a general
standard. Expired deviations must fail review until renewed or resolved.

## Security

Treat skills as software. Review instructions, scripts, network use, bundled
files, and requested tools. Do not accept skills or templates containing
secrets, opaque downloads, unpinned executable dependencies, or unexplained
broad permissions.
