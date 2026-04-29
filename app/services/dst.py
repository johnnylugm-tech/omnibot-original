"""Dialogue State Tracking (DST) - Phase 2"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime


class ConversationState(Enum):
    IDLE = "idle"
    INTENT_DETECTED = "intent_detected"
    SLOT_FILLING = "slot_filling"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class DialogueSlot:
    name: str
    value: Optional[str] = None
    required: bool = True
    prompt: str = ""  # Question to ask when missing


@dataclass
class DialogueState:
    """Represents the current state of a conversation (Phase 2)"""
    conversation_id: int
    current_state: ConversationState = ConversationState.IDLE
    primary_intent: Optional[str] = None
    sub_intents: List[str] = field(default_factory=list)
    slots: Dict[str, DialogueSlot] = field(default_factory=dict)
    turn_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def transition(self, new_state: ConversationState) -> "DialogueState":
        """Immutable state transition"""
        return DialogueState(
            conversation_id=self.conversation_id,
            current_state=new_state,
            primary_intent=self.primary_intent,
            sub_intents=list(self.sub_intents),
            slots=dict(self.slots),
            turn_count=self.turn_count + 1,
            last_updated=datetime.utcnow(),
        )

    def missing_slots(self) -> List[DialogueSlot]:
        """Return a list of required slots that are currently empty"""
        return [s for s in self.slots.values() if s.required and s.value is None]


class DSTManager:
    """Manages dialogue states and transitions (Phase 2)"""

    def __init__(self):
        # In production, this would be backed by Redis/DB
        self._states: Dict[int, DialogueState] = {}

    def get_state(self, conversation_id: int) -> DialogueState:
        if conversation_id not in self._states:
            self._states[conversation_id] = DialogueState(
                conversation_id=conversation_id)
        return self._states[conversation_id]

    def update_state(self, state: DialogueState) -> None:
        self._states[state.conversation_id] = state

    def process_turn(self, conversation_id: int, intent: Optional[str], slots: Dict[str, str]) -> DialogueState:
        state = self.get_state(conversation_id)

        # Simple transition logic based on Phase 2 spec
        if state.current_state == ConversationState.IDLE and intent:
            state.primary_intent = intent
            state.current_state = ConversationState.INTENT_DETECTED

        # Update slots
        for name, value in slots.items():
            if name in state.slots:
                state.slots[name].value = value

        # Check for missing slots
        if state.current_state in [ConversationState.INTENT_DETECTED, ConversationState.SLOT_FILLING]:
            if not state.missing_slots():
                state.current_state = ConversationState.PROCESSING
            else:
                state.current_state = ConversationState.SLOT_FILLING

        # Escalation logic (more than 3 turns in slot filling)
        if state.current_state == ConversationState.SLOT_FILLING and state.turn_count >= 3:
            state.current_state = ConversationState.ESCALATED

        state.turn_count += 1
        state.last_updated = datetime.utcnow()
        self.update_state(state)
        return state
