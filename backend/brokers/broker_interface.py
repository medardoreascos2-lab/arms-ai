from abc import ABC, abstractmethod


class BrokerInterface(ABC):


    @abstractmethod
    def submit_order(
        self,
        order
    ):
        pass
