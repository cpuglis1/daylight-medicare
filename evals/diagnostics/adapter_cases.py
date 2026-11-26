"""Typed fictional start states for manually requested Daylight diagnostic trials.

The normal advisor processes setup actions with AI permission off. History is
seeded through its visit-memory validator only, with no profile authority.
Authored calibration outputs and descriptive context never enter these inputs.
"""

# One native opening answer leaves coverage path undecided. The correction
# case records and replaces the ZIP using the actual Plans filter action.
STARTS = {
    'question_timing-pause-1': {
        'lineHash': '05142fec2be54835d84c9cfa01a1797d0332a9442f17262e53ebc1003749772c',
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
        'lineHash': 'f4dc629958206a14a974e6e1a82400c740f6db4c18e4a4811eea825f153b989d',
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
