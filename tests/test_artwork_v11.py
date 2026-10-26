"""Run beside tests/test_portraits.py after applying the package."""
from pathlib import Path

import portraits


def test_neutral_picker_order_and_faction_exclusion():
    doc=portraits.manifest()
    for code in doc['class_defaults']:
        choices=portraits.gallery({'type_code':code})
        matching=[r for r in choices if r['code']==code]
        expected=2 if code in {'BASE','SECTION','JG','PT'} else 4
        assert [r['variant'] for r in matching]==list(range(1,expected+1))
        assert all(r.get('faction')=='generic' for r in choices)
        assert all(r['id'] in doc['gallery_ids'] for r in choices)

def test_original_ruleset_has_only_neutral_portraits():
    doc=portraits.manifest()
    original={k:v for k,v in doc['official'].items() if k.startswith(('ft:','mt:'))}
    assert len(original)==31
    assert all(v.startswith('neutral-v11:') for v in original.values())
    assert all(doc['portraits'][v]['faction']=='generic' for v in original.values())

def test_hidden_legacy_faction_choice_still_resolves():
    doc=portraits.manifest()
    key='custom:SC:palette-v8-1'
    assert key not in doc['gallery_ids']
    design={'id':'neutral-picker-test','type_code':'SC'}
    choice={portraits.design_target(design):{'art':key}}
    assert portraits.resolve(design,choice)==doc['portraits'][key]

def test_midway_baseline_unchanged_and_twenty_new_hulls():
    doc=portraits.manifest()
    assert sum(key.startswith('midway-v11:') for key in doc['portraits'])==20
    assert doc['portraits']['palette-v8:nac-ft143']['file']=='ships/nac-ft143-palette-v8.webp'
    root=Path(portraits.__file__).parent
    for key in doc['gallery_ids']:
        assert (root/'static'/doc['portraits'][key]['file']).is_file()
