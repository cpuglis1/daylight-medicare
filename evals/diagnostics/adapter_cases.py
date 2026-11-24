"""Typed fictional start states for manually requested Daylight diagnostic trials.

The normal advisor processes setup actions with AI permission off. History is
seeded through its visit-memory validator only, with no profile authority.
Authored calibration outputs and descriptive context never enter these inputs.
"""

# One native opening answer leaves coverage path undecided. The correction
# case records and replaces the ZIP using the actual Plans filter action.
STARTS = {
    'question_timing-pause-1': {
        'lineHash': '3916532f4ad58588613b7b7395f024fbd1de6ba129dbfce934276c11864bc44a',
        'setup': [
            {'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}},
            {'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
            {'type': 'edit', 'id': 'T10'},
        ],
        'question': 'T10',
        'history': [],
        'fields': {'intent.goal': 'compare', 'intent.coveragePath': None},
    },
    'conversational_continuity-correction-1': {
        'lineHash': '06b46e7addc436445589f85b2e543d1b49c6ff0a45105a4e98143a42ff7e765e',
        'setup': [
            {'type': 'choice', 'id': 'T01', 'fields': {'choice': 'compare'}},
            {'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
            {'type': 'choice', 'id': 'T03', 'fields': {'zip': '34102'}},
            {'type': 'choice', 'id': 'T03', 'fields': {'zip': '34103'}},
        ],
        'history': [('My home ZIP is 34102.', '', ''),
                    ('I need to correct that. My home ZIP is 34103.', 'I have 34103 now.', '')],
        'fields': {'comparison.scope.zip': '34103'},
    },
}
