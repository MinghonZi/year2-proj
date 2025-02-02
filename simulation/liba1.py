import pybullet as bullet
import pandas as pd
import numpy as np
import logging
from enum import Enum
from typing import Iterable

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(funcName)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    # filename='liba1.log',
    # filemode='w',
    encoding='utf-8')

class A1:

    class EnumWithListMethod(Enum):
        @classmethod
        def list(cls):
            return list(map(lambda c: c.value, cls))

    class Leg(EnumWithListMethod):  # TODO: Use 3.11 enum.StrEnum to remove .value
        fr = 'front-right'
        fl = 'front-left'
        hr = 'hind-right'
        hl = 'hind-left'

    class Motor(EnumWithListMethod):  # TODO: Use 3.11 enum.StrEnum to remove .value
        h_aa = 'hip abduction/adduction'
        h_fe = 'hip flexion/extension'
        knee = 'knee'

    motor_indices = pd.DataFrame(dtype=np.int8, index = Motor.list(), columns = Leg.list(),
                        # front-right, front-left, hind-right, hind-left
        data = np.array([[     1     ,      6    ,     11    ,     16   ],    # hip abduction/adduction
                         [     3     ,      8    ,     13    ,     18   ],    # hip flexion/extension
                         [     4     ,      9    ,     14    ,     19   ]]))  # knee
    # Obtained by measuring the STL file of the thigh and calf. Both are 0.2mm.
    thigh_len  = 200
    shank_len  = 200
    hip_offset = 80   # TODO: Obtain more accurate value
    body_len   = 360  # TODO: Obtain more accurate value
    body_width = 200  # TODO: Obtain more accurate value


    def __init__(
    self,
    physics_client_id: int,
    base_position: Iterable[float] = [0, 0, 0.43],
    base_orientation: Iterable[float] = [0, 0, 0, 1]):
        self.in_physics_client = physics_client_id
        # Load the model in the given PyBullet physics client.
        import pybullet_data; bullet.setAdditionalSearchPath(pybullet_data.getDataPath())  # The A1 model is in the pybullet_data
        self.id = bullet.loadURDF(
            "a1/a1.urdf",
            base_position, base_orientation,
            physicsClientId = self.in_physics_client,
            flags = bullet.URDF_USE_SELF_COLLISION,
            useFixedBase = False)
        # Set initial postion of motors.
        bullet.setJointMotorControlArray(
            physicsClientId = self.in_physics_client,
            bodyUniqueId = self.id,
            jointIndices = self.motor_indices.loc[A1.Motor.h_aa.value, :],  # TODO: Use 3.11 enum.StrEnum to remove .value
            controlMode = bullet.POSITION_CONTROL,
            targetPositions = np.full(4, 0),)
        bullet.setJointMotorControlArray(
            physicsClientId = self.in_physics_client,
            bodyUniqueId = self.id,
            jointIndices = self.motor_indices.loc[A1.Motor.h_fe.value, :],  # TODO: Use 3.11 enum.StrEnum to remove .value
            controlMode = bullet.POSITION_CONTROL,
            targetPositions = np.full(4, 0.7),)
        bullet.setJointMotorControlArray(
            physicsClientId = self.in_physics_client,
            bodyUniqueId = self.id,
            jointIndices = self.motor_indices.loc[A1.Motor.knee.value, :],  # TODO: Use 3.11 enum.StrEnum to remove .value
            controlMode = bullet.POSITION_CONTROL,
            targetPositions = np.full(4, -0.7*2),)  # ensures that the toes are beneath the hips


    def motor_info(self):
        """
        A matrix contains motor information. The info is structured as
        Tuple(jointIndex, jointName, jointType, qIndex, uIndex, flags, jointDamping,
        jointFriction, jointLowerLimit, jointUpperLimit, jointMaxForce, jointMaxVelocity,
        linkName, jointAxis, parentFramePos, parentFrameOrn, parentIndex)

        See PyBullet document for getJointInfo().
        """
        return A1.motor_indices.applymap(lambda index: bullet.getJointInfo(self.id, index))


    def current_posture(self):
        return A1.motor_indices.applymap(lambda index: bullet.getJointState(self.id, index, self.in_physics_client)[0])


    def postural_control(self, yaw_angle=0., pitch_angle=0., roll_angle=0., Δz=0., reference_posture=None) -> None:
        """
        :param Δz:
            Height is not easily defined for a legged robot on uneven terrains; hence, z-coordinate of the toe
            relative to the coordinate system on the hip of each leg is used.
        :param reference_posture:
            A frame of reference which the attitude and position given by the other params is relative to
        """

        if reference_posture is None:
            # FIXME: Taking an angle of 0.0 and calculating it repeatedly with respect to the current posture,
            # it can be observed that the errors add up and the posture of the robot is slowly distorted.
            # Possible solution: decrease to 3 decimal places.
            posture = self.current_posture()
        else:
            posture = reference_posture.copy()

        for leg, θ in posture.items():  #! Pass by reference; modify θ will also modify the element in posture
            # θ is a tuple of three motor angular positions of one leg

            # Abbreviating to increase readability
            α = yaw_angle
            β = pitch_angle
            γ = roll_angle
            L = A1.body_len / 2
            W = A1.body_width / 2

            x, y, z = A1._forward_kinematics(leg, *θ)

            # Adjust height
            z -= Δz  # FIXME: Wrong algrithm.

            # x, y, z after rolling
            match leg:
                case A1.Leg.fr.value | A1.Leg.hr.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    roll = np.array([[ 1,  0,          0,          0                 ],
                                     [ 0,  np.cos(γ), -np.sin(γ),  W * np.cos(γ) - W ],
                                     [ 0,  np.sin(γ),  np.cos(γ),  W * np.sin(γ)     ],
                                     [ 0,  0,          0,          1                 ]])
                case A1.Leg.fl.value | A1.Leg.hl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    roll = np.array([[ 1,  0,          0,          0                 ],
                                     [ 0,  np.cos(γ), -np.sin(γ), -W * np.cos(γ) + W ],
                                     [ 0,  np.sin(γ),  np.cos(γ), -W * np.sin(γ)     ],
                                     [ 0,  0,          0,          1                 ]])
            x, y, z, _ = roll.dot(np.array([x, y, z, 1]))

            # x, z after pitching
            match leg:
                case A1.Leg.fr.value | A1.Leg.fl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    pitch = np.array([[ np.cos(β), -np.sin(β),  L * np.cos(β) - L ],
                                      [ np.sin(β),  np.cos(β),  L * np.sin(β)     ],
                                      [ 0,          0,          1                 ]])
                case A1.Leg.hr.value | A1.Leg.hl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    pitch = np.array([[ np.cos(β), -np.sin(β), -L * np.cos(β) + L ],
                                      [ np.sin(β),  np.cos(β), -L * np.sin(β)     ],
                                      [ 0,          0,          1                 ]])
            x, z, _ = pitch.dot(np.array([x, z, 1]))

            # x, y, z after yawing
            match leg:
                case A1.Leg.fr.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    yaw = np.array([[ np.cos(α), -np.sin(α),   0,   L * np.cos(α) - W * np.sin(α) - L ],
                                    [ np.sin(α),  np.cos(α),   0,   L * np.sin(α) + W * np.cos(α) - W ],
                                    [ 0,          0,           1,   0                                 ],
                                    [ 0,          0,           0,   1                                 ]])
                case A1.Leg.fl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    yaw = np.array([[ np.cos(α), -np.sin(α),   0,   L * np.cos(α) + W * np.sin(α) - L ],
                                    [ np.sin(α),  np.cos(α),   0,   L * np.sin(α) - W * np.cos(α) + W ],
                                    [ 0,          0,           1,   0                                 ],
                                    [ 0,          0,           0,   1                                 ]])
                case A1.Leg.hr.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    yaw = np.array([[ np.cos(α), -np.sin(α),   0,  -L * np.cos(α) - W * np.sin(α) + L ],
                                    [ np.sin(α),  np.cos(α),   0,  -L * np.sin(α) + W * np.cos(α) - W ],
                                    [ 0,          0,           1,   0                                 ],
                                    [ 0,          0,           0,   1                                 ]])
                case A1.Leg.hl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                    yaw = np.array([[ np.cos(α), -np.sin(α),   0,  -L * np.cos(α) + W * np.sin(α) + L ],
                                    [ np.sin(α),  np.cos(α),   0,  -L * np.sin(α) - W * np.cos(α) + W ],
                                    [ 0,          0,           1,   0                                 ],
                                    [ 0,          0,           0,   1                                 ]])
            x, y, z, _ = yaw.dot(np.array([x, y, z, 1]))

            θ[0], θ[1], θ[2] = A1._inverse_kinematics(leg, x, y, z)

            # If θ[0] or θ[1] or θ[2] exceeds its limits, aborting the method
            if not all([-0.803<θ[0]<0.803, -1.047<θ[1]<4.189, -2.697<θ[2]<-0.916]):
                logging.info('Motor limit reached')
                return

        # Control angular position of each motor
        for positions_of_one_leg, indices_of_one_leg in zip(posture.itertuples(index=False), A1.motor_indices.itertuples(index=False)):
            bullet.setJointMotorControlArray(
                physicsClientId = self.in_physics_client,
                bodyUniqueId = self.id,
                controlMode = bullet.POSITION_CONTROL,
                jointIndices = indices_of_one_leg,
                targetPositions = positions_of_one_leg,)


    @classmethod
    def _forward_kinematics(cls, leg: Leg, θ0, θ1, θ2):
        """
        θ0, θ1, θ2 ⇒ x, y, z

        :param θ0: angular position of hip abd/add motor
        :param θ1: angular position of hip fle/ext motor
        :param θ2: angular position of knee motor
        :return  : a tuple, (x, y, z), which is coordinates of the toe relative to the hip
        """

        # Abbreviating to increase readability
        l1 = cls.thigh_len
        l2 = cls.shank_len
        o  = cls.hip_offset
        h  =  l1 * np.cos(θ1) + l2 * np.cos(θ1 + θ2)  # distance from the toe to the top centre of the thigh rod

        x = -l1 * np.sin(θ1) - l2 * np.sin(θ1 + θ2)
        match leg:
            case A1.Leg.fr.value | A1.Leg.hr.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                y =  o * np.cos(θ0) - h * np.sin(θ0)
                z = -o * np.sin(θ0) - h * np.cos(θ0)
            case A1.Leg.fl.value | A1.Leg.hl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                y = -o * np.cos(θ0) - h * np.sin(θ0)
                z =  o * np.sin(θ0) - h * np.cos(θ0)

        return (x, y, z)


    @classmethod
    def _inverse_kinematics(cls, leg: Leg, x, y, z):
        """
        x, y, z ⇒ θ0, θ1, θ2

        :param x, y, z: coordinates of the toe relative to the hip
        :return       : a tuple, (θ0, θ1, θ2), which is angular position of three motors on a leg
        """

        # Abbreviating to increase readability
        l1 = cls.thigh_len
        l2 = cls.shank_len
        o  = cls.hip_offset
        h  = np.sqrt(z**2 + y**2 - o**2)

        cosθ2 = (-l1**2 - l2**2 + x**2 + h**2) / (2 * l1 * l2)
        sinθ2 = -np.sqrt(1 - cosθ2**2)  # takes negative suqare root, because the knee's position is specified as negative
        match leg:
            case A1.Leg.fr.value | A1.Leg.hr.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                θ0 = np.arctan2(np.abs(z), y) - np.arctan2(h, o)
            case A1.Leg.fl.value | A1.Leg.hl.value:  # TODO: Use 3.11 enum.StrEnum to remove .value
                θ0 = np.arctan2(h, o) - np.arctan2(np.abs(z), -y)
        θ1 = np.arccos((l1**2 + x**2 + h**2 - l2**2) / (2 * l1 * np.sqrt(x**2 + h**2))) - np.arctan2(x, h)
        θ2 = np.arctan2(sinθ2, cosθ2)

        return (θ0, θ1, θ2)
