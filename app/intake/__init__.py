"""
app.intake
----------
Founder intake package.

Provides the CLI questionnaire for collecting FounderContext before the
pipeline runs. This package is imported lazily — only when --intake is
present in sys.argv — so it never affects non-interactive invocations.
"""
