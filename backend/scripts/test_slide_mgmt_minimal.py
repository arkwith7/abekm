from app.services.presentation.enhanced_ppt_generator_service import enhanced_ppt_generator_service
from types import SimpleNamespace
import os

# Minimal DeckSpec-like object (populate required fields)
class Deck:
    def __init__(self):
        self.slides = []
        self.title = 'Test'
        self.topic = 'Test Topic'
        self.context_text = ''
        self.presentation_type = 'general'
        self.include_charts = False
        self.key_takeaways = []
        self.diagram = None
        self.summary = ''
        self.template_style = 'business'

slides = [
    SimpleNamespace(title="S1", bullets=[], key_message=""),
    SimpleNamespace(title="S2", bullets=[], key_message=""),
]
deck = Deck()
deck.slides = slides

# Build a base PPT from the two-slide deck
base_path = enhanced_ppt_generator_service.build_enhanced_pptx(deck, file_basename='tmp_sm_base', custom_template_path=None)
print('Base:', base_path, os.path.exists(base_path))

# Slide management: keep slide 0, insert a new slide after it (based on 0), then slide 1
slide_mgmt = [
    {'index': 0, 'original_index': 0, 'title': 'S1', 'is_enabled': True},
    {'index': 1, 'original_index': None, 'base_slide_index': 0, 'title': 'New', 'is_enabled': True},
    {'index': 2, 'original_index': 1, 'title': 'S2', 'is_enabled': True},
]

managed_path = enhanced_ppt_generator_service._apply_slide_management_to_ppt(base_path, slide_mgmt)
print('Managed:', managed_path, os.path.exists(managed_path))
