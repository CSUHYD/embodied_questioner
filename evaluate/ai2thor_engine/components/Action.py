
from ai2thor.controller import Controller

class BaseAction:

    def __init__(self):
        self.action_mapping = {
            # move agent
            "stand": self.stand,
            "crouch": self.crouch,
            "move_ahead": self.move_ahead,
            "move_back": self.move_back,
            "move_left": self.move_left,
            "move_right": self.move_right,
            "teleport": self.teleport,
            "rotate_left": self.rotate_left,
            "rotate_right": self.rotate_right,
            "look_up": self.look_up,
            "look_down": self.look_down,
            # move arm
            "move_arm": self.move_arm,
            "set_hand_radius": self.set_hand_radius,
            "arm_reset": self.arm_reset,
            # move object
            "pick_up": self.pick_up,
            "release": self.release,
            "put_in": self.put_in,
            "drop_out": self.drop_out,
            "throw_out": self.throw_out,
            "move_hand_object": self.move_hand_object,
            "rotate_hand_object": self.rotate_hand_object,
            # change object state
            "open": self.open,
            "close": self.close,
            "break_": self.break_,
            "cook": self.cook,
            "slice_": self.slice_,
            "toggle_on": self.toggle_on,
            "toggle_off": self.toggle_off,
            "dirty": self.dirty,
            "clean": self.clean,
            "fill": self.fill,
            "empty": self.empty,
            "use_up": self.use_up,
        }
    
    #--Move agent------------------------------------------------------------------------------------------------------------#
    def stand(self, controller):
        return controller.step(
            action="Stand",
        )
    
    def crouch(self, controller):
        return controller.step(
            action="Crouch",
        )
        
    def move_ahead(self, controller: Controller, moveMagnitude=0.25):
        return controller.step(
            action="MoveAhead",
            moveMagnitude=moveMagnitude,
            # returnToStart=True,
        )
    
    def move_back(self, controller, moveMagnitude=0.25):
        return controller.step(
            action="MoveBack",
            moveMagnitude=moveMagnitude,
            # returnToStart=True,
        )
    
    def move_left(self, controller, moveMagnitude=0.25):
        controller.step(
            action="RotateLeft",
            degrees=90
        )
        controller.step(
            action="MoveAhead",
            moveMagnitude=moveMagnitude,
        )
        controller.step(
            action="RotateRight",
            degrees=90
        )
    
    def move_right(self, controller, moveMagnitude=0.25):
        controller.step(
            action="RotateRight",
            degrees=90
        )
        controller.step(
            action="MoveAhead",
            moveMagnitude=moveMagnitude,
        )
        controller.step(
            action="RotateLeft",
            degrees=90
        )
    
    def teleport(self, controller, position, rotation, horizon=60):
        return controller.step(
            action='Teleport',
            position=position,
            rotation=rotation,
            horizon=horizon,
        )
    
    def rotate_left(self, controller, degrees=90):
        return controller.step(
            action="RotateLeft",
            degrees=degrees
        )
    
    def rotate_right(self, controller, degrees=90):
        return controller.step(
            action="RotateRight",
            degrees=degrees
        )
    
    def look_up(self, controller, degrees=10):
        return controller.step(action='LookUp', degrees=degrees)
    
    def look_down(self, controller, degrees=10):
        return controller.step(action='LookDown', degrees=degrees)
    
    #--Move agent------------------------------------------------------------------------------------------------------------#


    #--Move arm--------------------------------------------------------------------------------------------------------------#
    def move_arm(self, controller, position):
        return controller.step(
            action="MoveArm",
            position=dict(x=0, y=0.5, z=0),
            coordinateSpace="armBase",
            restrictMovement=False,
            speed=1,
            returnToStart=True,
            fixedDeltaTime=0.02
        )
    
    def set_hand_radius(self, controller, radius=0.1):
        '''
        The radius on the agent's "magnet sphere" hand, in meters. 
        Valid values are in (0.04:0.5)meters.
        '''
        return controller.step(
            action="SetHandSphereRadius",
            radius=radius
        )
    
    def arm_reset(self, controller):
        try:
            return controller.step(
                action="MoveArm",
                position=dict(x=0, y=0, z=-1),
                coordinateSpace="armBase",
                restrictMovement=False,
                speed=1,
                returnToStart=True,
                fixedDeltaTime=0.02
            )
        except Exception as e:
            print(e)
            return None
    #--Move arm--------------------------------------------------------------------------------------------------------------#
    

    #--Move object-----------------------------------------------------------------------------------------------------------#
    def pick_up(self, controller, object_id):
        return controller.step(
            action="PickupObject",
            objectId=object_id,
            forceAction=False,
            manualInteract=False
        )

    def release(self, controller, ):
        return controller.step(action="ReleaseObject")
    
    def put_in(self, controller, object_id):
        return controller.step(
            action="PutObject",
            objectId=object_id,
            forceAction=False,
            placeStationary=True
        )
    
    def drop_out(self, controller):
        return controller.step(
            action="DropHandObject",
            forceAction=False
        )
    
    def throw_out(self, controller):
        return controller.step(
            action="ThrowObject",
            moveMagnitude=150.0, # 力度
            forceAction=False
        )
    
    def move_hand_object(self, controller, ahead=0.1, right=0.05, up=0.12):
        # controller.step(
        #     action="MoveHeldObjectAhead",
        #     moveMagnitude=moveMagnitude,
        #     forceVisible=False
        # )
        # # Other supported directions
        # controller.step("MoveHeldObjectBack")
        # controller.step("MoveHeldObjectLeft")
        # controller.step("MoveHeldObjectRight")
        # controller.step("MoveHeldObjectUp")
        # controller.step("MoveHeldObjectDown")
        return controller.step(
            action="MoveHeldObject",
            ahead=ahead,
            right=right,
            up=up,
            forceVisible=False
        )
    
    def rotate_hand_object(self, controller, pitch=90, yaw=25, roll=45):
        return controller.step(
            action="RotateHeldObject",
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            # rotation=dict(x=90, y=15, z=25)
        )
    #--Move object------------------------------------------------------------------------------------------------------------#
    

    #--Change object state----------------------------------------------------------------------------------------------------#    
    def open(self, controller, object_id):
        return controller.step(
            action="OpenObject",
            objectId=object_id, # "Book|0.25|-0.27|0.95",
            openness=1,
            forceAction=False
        )
    
    def close(self, controller, object_id):
        return controller.step(
            action="CloseObject",
            objectId=object_id, # "Book|0.25|-0.27|0.95",
            forceAction=False
        )

    def break_(self, controller, object_id):
        return controller.step(
            action="BreakObject",
            objectId=object_id, 
            forceAction=False
        )
        
    def cook(self, controller, object_id):
        return controller.step(
            action="CookObject",
            objectId=object_id, 
            forceAction=False
        )
    
    def slice_(self, controller, object_id="Potato|0.25|-0.27|0.95"):
        return controller.step(
            action="SliceObject",
            objectId=object_id, 
            forceAction=False
        )
    
    def toggle_on(self, controller, object_id):
        return controller.step(
            action="ToggleObjectOn",
            objectId=object_id, 
            forceAction=False
        )
    
    def toggle_off(self, controller, object_id):
        return controller.step(
            action="ToggleObjectOff",
            objectId=object_id, 
            forceAction=False
        )
    
    def dirty(self, controller, object_id):
        return controller.step(
            action="DirtyObject",
            objectId=object_id,
            forceAction=False
        )
    
    def clean(self, controller, object_id):
        return controller.step(
            action="CleanObject",
            objectId=object_id,
            forceAction=False
        )
    
    def fill(self, controller, object_id):
        return controller.step(
            action="FillObjectWithLiquid",
            objectId=object_id,
            forceAction=False
        )
    
    def empty(self, controller, object_id):
        return controller.step(
            action="EmptyLiquidFromObject",
            objectId=object_id,
            forceAction=False
        )

    def use_up(self, controller, object_id):
        return controller.step(
            action="UseUpObject",
            objectId=object_id,
            forceAction=False
        )
    
    #--Change object state----------------------------------------------------------------------------------------------------------------------#