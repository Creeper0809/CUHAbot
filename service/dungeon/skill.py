class Skill:
    def __init__(self, skill_model,components):
        self.__skill_model = skill_model
        self.__components = sorted(components, key=lambda x: x.priority)

    def on_turn(self, attacker, target):
        logs = []
        for component in self.__components:
            logs.append(component.on_turn(attacker,target))
        return "\n".join(logs)

    def on_turn_end(self, attacker, target):
        logs = []
        for component in self.__components:
            logs.append(component.on_turn_end(attacker, target))
        return "\n".join(logs)

    def on_turn_start(self, attacker, target):
        logs = []
        for component in self.__components:
            logs.append(component.on_turn_start(attacker, target))
        return "\n".join(logs)


