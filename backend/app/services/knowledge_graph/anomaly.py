_ELEVATED_Z = 1.0
_REDUCED_Z = -1.0


def classify_anomaly(z: float, invert: bool = False) -> str:
    """Classify a z-score as 'elevated', 'typical', or 'reduced' relative to a location's
    own baseline. `invert=True` for indicators where a LOWER value means higher risk (e.g.
    NDVI: less vegetation is worse), so the same +-1.0 z thresholds still map to the
    intuitive risk direction."""
    if invert:
        z = -z
    if z >= _ELEVATED_Z:
        return "elevated"
    if z <= _REDUCED_Z:
        return "reduced"
    return "typical"
