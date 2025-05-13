class Skill:
    def __init__(self, skill_model,components):
        self.__skill_model = skill_model
        self.__components = sorted(components, key=lambda x: x.priority)

    def on_turn(self, attacker, target):
        log = ""
        for component in self.__components:
            log += component.on_turn(attacker,target,self.__skill_model.name)
            log += "\n"
        return log


    def on_turn_end(self, attacker, target):
        log = ""
        for component in self.__components:
            log += component.on_turn_end(attacker, target, self.__skill_model.name)
            log += "\n"
        return log

    def on_turn_start(self, attacker, target):
        log = ""
        for component in self.__components:
            log += component.on_turn_start(attacker, target, self.__skill_model.name)
            log += "\n"
        return log


