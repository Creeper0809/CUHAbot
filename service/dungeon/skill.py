class Skill:
    def __init__(self, skill_model, components):
        self._skill_model = skill_model
        self._components = sorted(components, key=lambda x: x.priority)

    @property
    def skill_model(self):
        """스킬 모델 반환"""
        return self._skill_model

    @property
    def name(self) -> str:
        """스킬 이름"""
        return self._skill_model.name

    @property
    def description(self) -> str:
        """스킬 설명"""
        return self._skill_model.description or ""

    @property
    def id(self) -> int:
        """스킬 ID"""
        return self._skill_model.id

    def on_turn(self, attacker, target):
        logs = []
        for component in self._components:
            logs.append(component.on_turn(attacker, target))
        return "\n".join(logs)

    def on_turn_end(self, attacker, target):
        logs = []
        for component in self._components:
            logs.append(component.on_turn_end(attacker, target))
        return "\n".join(logs)

    def on_turn_start(self, attacker, target):
        logs = []
        for component in self._components:
            logs.append(component.on_turn_start(attacker, target))
        return "\n".join(logs)


