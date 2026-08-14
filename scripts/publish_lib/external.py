"""Locate external local services that godogen wires into published repos.

Two of these exist -- the knowledge graph and the audio studio -- and they are
the same kind of thing: a separate repo, cloned somewhere on this machine,
running as a local service. Neither can be vendored. Both keep their real
payload out of git: multi-gigabyte models and an accumulated library that is
machine-local by nature. A submodule would hand you an empty shell.

So they are found by path, and the rules are shared:

  - The environment variable is authoritative. Set it wrong and that is an
    error, not a reason to quietly use a different installation.
  - Otherwise search the checkout, its parent, and ~/.godogen, under every
    name the repo is commonly cloned as -- `git clone <url>` produces the
    repository name, and most people do not rename it.
  - Nothing found is not an error. Publishing without a service produces a
    repo that works, with less in it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Where an external checkout plausibly lives, most specific first.
ANCHORS: tuple[Path, ...] = (
    REPO_ROOT,
    REPO_ROOT.parent,
    Path.home() / ".godogen",
)


class NotFound(Exception):
    """An environment variable named a location that is not an installation."""


@dataclass(frozen=True)
class Tool:
    name: str
    env_var: str
    dir_names: tuple[str, ...]
    markers: tuple[str, ...]
    repo: str
    purpose: str

    def is_installed(self, path: Path) -> bool:
        try:
            return all((path / marker).exists() for marker in self.markers)
        except OSError:
            return False

    def candidates(self) -> list[Path]:
        return [anchor / name for anchor in ANCHORS for name in self.dir_names]

    def find_all(self, environ: dict[str, str] | None = None) -> list[Path]:
        """Every installation on this machine, in search order.

        More than one is worth saying out loud. The first wins, and the first
        anchor is the godogen checkout -- so cloning a second copy into it
        silently shadows the one the user already had, along with its
        multi-hundred-megabyte model cache. Nothing else would surface that:
        the index builds fine against the new empty one.
        """
        environ = os.environ if environ is None else environ
        override = environ.get(self.env_var)
        if override:
            path = Path(override)
            return [path] if self.is_installed(path) else []
        seen: list[Path] = []
        for candidate in self.candidates():
            if self.is_installed(candidate) and candidate not in seen:
                seen.append(candidate)
        return seen

    def find(self, environ: dict[str, str] | None = None) -> Path | None:
        environ = os.environ if environ is None else environ

        override = environ.get(self.env_var)
        if override:
            path = Path(override)
            if not self.is_installed(path):
                raise NotFound(
                    f"{self.env_var}={override} is not a {self.name} installation "
                    f"(expected {', '.join(self.markers)} inside it)"
                )
            return path

        for candidate in self.candidates():
            if self.is_installed(candidate):
                return candidate
        return None

    def shadow_warning(self, environ: dict[str, str] | None = None) -> str | None:
        """A note when more than one installation exists, or None."""
        found = self.find_all(environ)
        if len(found) < 2:
            return None
        shadowed = "\n".join(f"           {p}" for p in found[1:])
        return (
            f"note: {len(found)} {self.name} installations found. Using:\n"
            f"           {found[0]}\n"
            f"         Ignoring:\n{shadowed}\n"
            f"         Set {self.env_var} to choose deliberately."
        )

    def missing_message(self) -> str:
        return (
            f"warning: no {self.name} installation found -- {self.purpose}\n"
            f"         Fix with:\n"
            f"           git clone {self.repo}\n"
            f"         from the godogen checkout, or set {self.env_var}."
        )


KG = Tool(
    name="kg",
    env_var="GODOGEN_KG_HOME",
    # `git clone` names the directory after the repo, and most people leave it.
    dir_names=("kg", "Multi-knowledgeGraph"),
    markers=("main.js", "hooks"),
    repo="https://github.com/ddwolfer/Multi-knowledgeGraph kg",
    purpose="publishing without knowledge wiring; the game repo starts and stays amnesic.",
)

ACE = Tool(
    name="ACE Studio",
    env_var="ACE_STUDIO_HOME",
    dir_names=("ACE_Studio", "ace-studio"),
    markers=("mcp-server", "library"),
    repo="https://github.com/ddwolfer/ACE_Studio",
    purpose="publishing without audio; the game gets no sound effects or music.",
)

TOOLS = (KG, ACE)
