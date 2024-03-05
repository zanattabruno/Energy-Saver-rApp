class UE:
    def __init__(self, ID, demand, channel_gain):
        self.ID = ID
        self.demand = demand
        self.channel_gain = channel_gain
    
    def __str__(self):
        return "User: {} \t with demand: {}".format(self.ID, self.demand)

    def E2N_channel_gain(self, E2N_ID):
        return self.channel_gain[E2N_ID]

class E2_Node:
    def __init__(self, ID, BW, max_power, RF_consumption, Power_amp_efficiency):
        self.ID = ID
        self.BW = BW
        self.max_power = max_power
        self.RF_consumption = RF_consumption
        self.Power_amp_efficiency = Power_amp_efficiency
    def __str__(self):
        return "E2 Node {} \t with BW {} \t PW {} \t RF {} \t Eff {}".format(self.ID, 
                                                                            self.BW, 
                                                                            self.max_power,
                                                                            self.RF_consumption,
                                                                            self.Power_amp_efficiency)