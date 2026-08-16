// NOVA navigation model -- Section 16.
//
// WHAT THIS IS NOT, deliberately and by instruction:
//   not a router, not a routing abstraction, not a state-management layer,
//   not an application framework. There is no route registry, no middleware,
//   no history integration, no subscriptions and no lifecycle. Everything below
//   is a pure function over the IA map. If this file ever grows those things,
//   Web Components will have become NOVA's application framework by accretion,
//   which D-13 leaves to James.
//
// The single security-relevant property it encodes is I-03: a location in one
// scope may not offer a path into a sibling scope. The UI cannot *enforce* that
// -- the PDP does. What the UI must not do is OFFER a path the policy layer
// would refuse, because an interface that offers unreachable destinations
// teaches James that scopes are connected when they are not.

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

export function parsePath(path) {
  return String(path || "").split("/").filter(Boolean);
}

export function pathString(segments) {
  return segments.join("/");
}

// Documentation keys in the map are prefixed with "$" and are not scopes. They
// are filtered in exactly one place -- here -- so no traversal can accidentally
// present one as a destination.
const isScopeKey = (key) => !key.startsWith("$");

export function scopeChildren(node) {
  const children = node && node.children ? node.children : {};
  return Object.keys(children).filter(isScopeKey);
}

export function nodeAt(map, segments) {
  let node = { children: map.scopes };
  for (const seg of segments) {
    if (!isScopeKey(seg)) return null;
    if (!node || !node.children || !node.children[seg]) return null;
    node = node.children[seg];
  }
  return node;
}

export function exists(map, segments) {
  return segments.length > 0 && nodeAt(map, segments) !== null;
}

function isAncestor(a, b) {
  return b.length > a.length && a.every((s, i) => b[i] === s);
}

// ---------------------------------------------------------------------------
// Relation between two locations
// ---------------------------------------------------------------------------

export const RELATION = {
  SAME: "same",
  DESCEND: "descend",
  ASCEND: "ascend",
  SWITCH: "switch", // siblings, cousins, cross-area -- everything not on one line of descent
};

export function relation(from, to) {
  if (from.length === to.length && from.every((s, i) => s === to[i])) return RELATION.SAME;
  if (isAncestor(from, to)) return RELATION.DESCEND;
  if (isAncestor(to, from)) return RELATION.ASCEND;
  return RELATION.SWITCH;
}

// ---------------------------------------------------------------------------
// What navigation may offer from a location
// ---------------------------------------------------------------------------

/**
 * The destinations navigation may present from `at`: its ancestors and its
 * direct children. Never a sibling, never a cousin, never another area.
 *
 * This is the function the sibling-path tests interrogate. Nothing else in the
 * demonstration constructs a destination list.
 */
export function navigationOffers(map, at) {
  const offers = [];

  for (let i = 0; i < at.length; i++) {
    const segments = at.slice(0, i + 1);
    if (i < at.length - 1) {
      offers.push({ segments, relation: RELATION.ASCEND, label: labelFor(map, segments) });
    }
  }

  const here = at.length ? nodeAt(map, at) : { children: map.scopes };
  for (const key of scopeChildren(here)) {
    const segments = [...at, key];
    offers.push({ segments, relation: RELATION.DESCEND, label: labelFor(map, segments) });
  }

  return offers;
}

export function labelFor(map, segments) {
  const node = nodeAt(map, segments);
  return node ? node.label : segments[segments.length - 1];
}

// ---------------------------------------------------------------------------
// Requesting a move
// ---------------------------------------------------------------------------

export const OUTCOME = {
  ALLOWED: "allowed",
  NEEDS_EXPLICIT_SWITCH: "needs-explicit-switch",
  UNREACHABLE: "unreachable",
};

/**
 * Ask to move from `from` to `to`.
 *
 * A move along one line of descent is ordinary navigation. Anything else --
 * sibling, cousin, another area -- is refused as implicit navigation and
 * returned as requiring an explicit switch. CONTEXT_ARCHITECTURE.md section 144:
 * "Requested scope is a sibling of the active one | Deny the implicit path;
 * require explicit switch."
 */
export function requestNavigation(map, from, to) {
  if (!exists(map, to)) {
    return { outcome: OUTCOME.UNREACHABLE, reason: "no such scope" };
  }

  const rel = relation(from, to);
  if (rel === RELATION.SWITCH) {
    return {
      outcome: OUTCOME.NEEDS_EXPLICIT_SWITCH,
      relation: rel,
      reason:
        "Sibling scopes have no path between them. Switching context is an explicit act, " +
        "not a navigation step.",
      authority: "I-03; CONTEXT_ARCHITECTURE.md section 144",
    };
  }

  return { outcome: OUTCOME.ALLOWED, relation: rel };
}

/**
 * An explicit switch, which is what the caller must perform after
 * requestNavigation refuses. It still returns a request for confirmation --
 * confirming is James's act, and this function performs nothing.
 *
 * Switching context authorizes nothing in the destination. Resolving *which*
 * scope is meant is disambiguation, never authorization.
 */
export function explicitSwitch(map, from, to) {
  if (!exists(map, to)) return { outcome: OUTCOME.UNREACHABLE, reason: "no such scope" };
  return {
    outcome: OUTCOME.ALLOWED,
    requiresConfirmation: true,
    from: pathString(from),
    to: pathString(to),
    grantsNothing: true,
  };
}

// ---------------------------------------------------------------------------
// Intent resolution -- ask, never guess
// ---------------------------------------------------------------------------

export const INTENT = { UNAMBIGUOUS: "unambiguous", AMBIGUOUS: "ambiguous", NONE: "none" };

/**
 * Given candidate scopes an instruction could mean, decide whether NOVA may
 * proceed or must ask.
 *
 * CONTEXT_ARCHITECTURE.md section 101: NOVA asks only when interpretations
 * differ *materially*, and does not ask when the alternatives are equivalent in
 * effect. So two candidates alone do not force a question -- two candidates
 * whose consequences differ do.
 */
export function resolveIntent(map, candidates) {
  if (!candidates.length) return { status: INTENT.NONE };
  if (candidates.length === 1) return { status: INTENT.UNAMBIGUOUS, chosen: candidates[0] };

  const material = candidates.filter((c) => {
    const node = nodeAt(map, parsePath(c));
    return node && node.material === true;
  });

  if (material.length > 1) {
    return {
      status: INTENT.AMBIGUOUS,
      candidates,
      reason: "The alternatives differ materially. NOVA asks rather than choosing.",
      authority: "CONTEXT_ARCHITECTURE.md sections 101-110, 142",
    };
  }

  return {
    status: INTENT.AMBIGUOUS,
    candidates,
    reason: "More than one scope matches. NOVA asks rather than choosing.",
    authority: "CONTEXT_ARCHITECTURE.md section 142",
  };
}

// ---------------------------------------------------------------------------
// Capabilities
// ---------------------------------------------------------------------------

export function isNavigable(map, capability) {
  const entry = map.capabilities[capability];
  return Boolean(entry && entry.navigable);
}

/** Capabilities that may appear in navigation. The excluded ones have no location. */
export function navigableCapabilities(map) {
  return Object.keys(map.capabilities).filter((c) => map.capabilities[c].navigable);
}

/** The disclosure level a location sits at. Never exceeds the navigable maximum. */
export function disclosureLevel(map, at, view) {
  if (view === "activity") return 4;
  if (at.length === 0) return map.disclosure.default_level;
  if (at.length <= 1) return 2;
  return 3;
}
