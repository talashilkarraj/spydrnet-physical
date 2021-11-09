
import logging
import math
from pprint import pformat, pprint
from spydrnet_physical.util.shell import launch_shell

import yaml
from spydrnet_physical.util import OpenFPGA_Placement_Generator

logger = logging.getLogger('spydrnet_logs')

AREA, WIDTH, HEIGHT = 0, 1, 2
CPP = 4
SC_HEIGHT = 4


class initial_placement(OpenFPGA_Placement_Generator):

    def __init__(self, grid, netlist, library, top_module, debug=False,
                 areaFile=None, padFile=None, gridIO=False, shapingConf=None):
        super().__init__(grid, netlist, library, top_module)

        self.sizeX = grid[0]
        self.sizeY = grid[1]
        self.PlacementDB = []
        self.PlacementDBKey = {}
        self.GPIOPlacmentKey = []
        self.debug = debug

        self.get_default_configuration()

        self.areaFile = areaFile
        self.padFile = padFile
        self.gridIO = gridIO
        self.PadNames = {}

        self.skipChannels = False

        # Color Setting
        self.CLB_COLOR = "#f4f0e6"
        self.CBX_COLOR = "#d9d9f3"
        self.CBY_COLOR = "#a8d0db"
        self.SB_COLOR = "#ceefe4"
        self.PAD_COLOR = "#204969"
        self.GRID_IO_COLOR = "#ff8000"

        # Pads Related
        self.pad_w = 80
        self.pad_h = 10
        if shapingConf:
            self.update_default_configuration(shapingConf)

    def create_placement(self):
        """
        Overrides the base method to create placement information
        """
        print("Running initial placement")
        self.SC_RATIO = (SC_HEIGHT/CPP)
        self.ComputeGrid(skipChannels=False)
        self.CreateDatabase()
        visited = []
        for instance_name, instance_info in self.PlacementDBKey.items():
            bbox = instance_info["bbox"]
            instance = next(self._top_module.get_instances(instance_name))
            module = instance.reference
            if len(instance_info["shape"]) == 1:
                if not module.name in visited:
                    llx, lly, w, h = instance_info["shape"][0]
                    module.properties["WIDTH"] = float(w)*CPP
                    module.properties["HEIGHT"] = float(h)*SC_HEIGHT

                instance.properties["LOC_X"] = bbox[0]*CPP
                instance.properties["LOC_Y"] = bbox[1]*SC_HEIGHT
            else:
                if not module.name in visited:
                    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
                    module.properties["WIDTH"] = float(w)*CPP
                    module.properties["HEIGHT"] = float(h)*SC_HEIGHT
                instance.properties["LOC_X"] = bbox[0]*CPP
                instance.properties["LOC_Y"] = bbox[1]*SC_HEIGHT

        self._top_module.properties["WIDTH"] = 500*CPP
        self._top_module.properties["HEIGHT"] = 500*SC_HEIGHT

    def update_default_configuration(self, shapingConf):
        with open(shapingConf, "r") as file:
            for eachKey, eachValue in yaml.load(file, Loader=yaml.FullLoader).items():
                setattr(self, eachKey, eachValue)

    def get_default_configuration(self):
        # Grid clb shape
        self.SC_RATIO = 1  # This is SC_HEIGHT/CPP of stadard cell
        self.GRID_CLB_RATIO = 1  # This is actual dimension of the CLB unit width/height

        # Connection box size
        self.GRID_RATIO_X, self.GRID_RATIO_Y = 2, 2
        self.CBX_WIDTH_RATIO, self.CBY_HEIGHT_RATIO = 1, 1

        # Channel spacing between blocks
        self.CLB_CHAN_T, self.CLB_CHAN_B = 0, 0
        self.CLB_CHAN_L, self.CLB_CHAN_R = 0, 0

        self.CBX_CHAN_T, self.CBX_CHAN_B = 0, 0
        self.CBX_CHAN_L, self.CBX_CHAN_R = 0, 0

        self.CBY_CHAN_T, self.CBY_CHAN_B = 0, 0
        self.CBY_CHAN_L, self.CBY_CHAN_R = 0, 0

        self.gridIO_MT, self.gridIO_MB = 0, 0
        self.gridIO_ML, self.gridIO_MR = 0, 0

        self.gridIO_HT, self.gridIO_HB = 0, 0
        self.gridIO_WL, self.gridIO_WR = 0, 0

        self.GRID_IOV_H_RATIO = 1
        self.GRID_IOH_W_RATIO = 1

        # TODO: Deprecate this
        self.GPIO_CHAN_X, self.GPIO_CHAN_Y = 0, 0
        self.GPIO_WIDTH, self.GPIO_HEIGHT = 40, 8

    def get_variables(self):
        return {
            "CLB_COLOR": self.CLB_COLOR,
            "CBX_COLOR": self.CBX_COLOR,
            "CBY_COLOR": self.CBY_COLOR,
            "SB_COLOR": self.SB_COLOR,
            "PAD_COLOR": self.PAD_COLOR,
            "GRID_IO_COLOR": self.GRID_IO_COLOR,
            "CORE_BBOX": (0, 0, int(self.CLB_GRID_X*(self.sizeX+1)),
                          int(self.CLB_GRID_Y*(self.sizeY+1)))
        }

    def figSize(self):
        size = (4+(1*self.sizeX), 4+(1*self.sizeY))
        if self.sizeX < 16:
            dpi = 300
        elif self.sizeX < 64:
            dpi = 100
        else:
            dpi = 50
        return {"size": size, "dpi": dpi}

    def snapDims(self, num, dim=2):
        return int(math.ceil(num/dim)*dim)

    def ComputeGrid(self, skipChannels=False):
        self.skipChannels = skipChannels
        if self.areaFile:
            BlockArea = {}
            for eachLine in open(self.areaFile, "r"):
                module, dims = eachLine.split(" ", 1)
                BlockArea[module] = list(map(float, list(dims.split())))
            self.CLB_DIM = BlockArea["grid_clb_1__1_"]
            self.CB_DIM = BlockArea["cbx_1__1_"]
            # self.CLB_DIM = math.floor(BlockArea["grid_clb_1__1_"][1]*0.5)*2
            # self.CB_DIM = [self.CLB_DIM*0.6, 0, 0]
        else:
            self.CLB_DIM = [2500, 24*8, 24]
            self.CB_DIM = [2500*0.6, 0, 0]

        # Snap CLB Height and Width to next Multiple of 2
        self.CLB_UNIT = math.sqrt(
            self.CLB_DIM[AREA]/(self.GRID_CLB_RATIO*self.SC_RATIO))

        self.CLB_H = self.snapDims(self.CLB_UNIT, 2)
        self.CLB_W = self.snapDims(self.CLB_DIM[AREA]/self.CLB_H, 2)

        self.CLB_GRID_X = self.snapDims(self.CLB_W*self.GRID_RATIO_X, 2)
        self.CLB_GRID_Y = self.snapDims(self.CLB_H*self.GRID_RATIO_Y, 2)

        self.CBX_W = self.snapDims(self.CLB_W*self.CBX_WIDTH_RATIO, 2)
        self.CBX_H = self.CLB_GRID_Y-self.CLB_H

        self.CBY_W = self.CLB_GRID_X-self.CLB_W
        self.CBY_H = self.snapDims(self.CLB_H*self.CBY_HEIGHT_RATIO, 2)

        self.SB_W = self.CLB_GRID_X - self.CBX_W
        self.SB_H = self.CLB_GRID_Y - self.CBY_H
        self.SIDE_X = self.CLB_GRID_X - self.CLB_W
        self.SIDE_Y = self.CLB_GRID_Y - self.CLB_H

        self.GRID_IOV_H = self.CLB_H*self.GRID_IOV_H_RATIO
        self.GRID_IOH_W = self.CLB_W*self.GRID_IOH_W_RATIO

        if self.debug:
            print(f"self.CLB_W {self.CLB_W}")
            print(f"self.CLB_H {self.CLB_H}")
            print(f"self.CLB_GRID_X {self.CLB_GRID_X}")
            print(f"self.CLB_GRID_Y {self.CLB_GRID_Y}")
            print(f"self.CBX_W {self.CBX_W}")
            print(f"self.CBX_H {self.CBX_H}")
            print(f"self.CBY_W {self.CBY_W}")
            print(f"self.CBY_H {self.CBY_H}")
            print(f"self.SB_W {self.SB_W}")
            print(f"self.SB_H {self.SB_H}")

        if self.padFile:
            if os.path.exists(self.padFile):
                print(f"Found PinMapFile {self.padFile}")
                df_pinMap = pd.read_csv(self.padFile)
                df_pinMap.rename(columns=lambda x: x.strip(), inplace=True)
                self.PadNames["L"] = df_pinMap["Remark"]
                self.PadNames["T"] = df_pinMap["Remark.1"]
                self.PadNames["R"] = df_pinMap["Remark.2"]
                self.PadNames["B"] = df_pinMap["Remark.3"]
                self.NumOfPads = len(df_pinMap.index)

    def CreateDatabase(self):
        # Create Blocks
        for x in range(self.sizeX+1):
            for y in range(self.sizeY+1):
                self.add_sb(x, y)
                if x < self.sizeY:
                    self.add_cbx(x, y)
                if y < self.sizeX:
                    self.add_cby(x, y)
                if (x < self.sizeX) and (y < self.sizeY):
                    self.add_clb(x, y)

                # Create gridIOs
                if self.gridIO:
                    if (y == self.sizeY) and (x < self.sizeX):
                        self.add_gridIOH(x, y, side="top")
                    if (y == 0) and (x < self.sizeX):
                        self.add_gridIOH(x, y, side="bottom")
                    if (x == 0) and (y < self.sizeY):
                        self.add_gridIOV(x, y, side="left")
                    if (x == self.sizeX) and (y < self.sizeY):
                        self.add_gridIOV(x, y, side="right")

        # Create Pins
        if self.PadNames:
            for side in ["L", "T", "R", "B"]:
                for i in range(self.NumOfPads):
                    self.add_pad(side, i, self.PadNames[side][i])
        return self.PlacementDB

    def add_clb(self, xi, yi, lbl=None):
        x, y = (xi+1)*self.CLB_GRID_X, (yi+1)*self.CLB_GRID_Y
        llx = x-self.snapDims(self.CLB_W*0.5)
        lly = y-self.snapDims(self.CLB_H*0.5)
        W1 = self.CLB_W
        H1 = self.CLB_H
        initShape = [(llx, lly, W1, H1)]

        if not self.skipChannels:
            llx += self.CLB_CHAN_L
            lly += self.CLB_CHAN_B
            W1 = self.CLB_W-self.CLB_CHAN_L-self.CLB_CHAN_R
            H1 = self.CLB_H-self.CLB_CHAN_T-self.CLB_CHAN_B
        block_name = f"grid_clb_{xi+1}__{yi+1}_"
        short_block_name = f"LB_{xi+1}_{yi+1}"
        COLOR = self.CLB_COLOR
        points = [0, 0, 0, self.CLB_H, self.CLB_W, self.CLB_H, self.CLB_W, 0]
        self.PlacementDB.append(block_name)
        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly,
                                                    llx+W1, lly+H1],
                                           "points": points,
                                           "module": "grid_clb_1__1_",
                                           "center": [x, y],
                                           "color": COLOR,
                                           "shape": [(llx, lly, W1, H1)],
                                           "initShape": initShape,
                                           "xi": xi,
                                           "yi": yi}

    def add_cbx(self, xi, yi, lbl=None):
        x, y = (xi+1)*self.CLB_GRID_X, (yi+1)*self.CLB_GRID_Y
        llx = x-self.snapDims((self.CBX_W)*0.5)
        lly = y-self.snapDims((self.CLB_H*0.5)+self.CBX_H)
        W1 = self.CBX_W
        H1 = self.CBX_H
        initShape = [(llx, lly, W1, H1)]

        if not self.skipChannels:
            llx += self.CBX_CHAN_L
            lly += self.CBX_CHAN_B
            W1 = self.CBX_W-self.CBX_CHAN_L-self.CBX_CHAN_R
            H1 = self.CBX_H-self.CBX_CHAN_T-self.CBX_CHAN_B

        block_name = f"cbx_{xi+1}__{yi}_"
        short_block_name = f"CX_{xi+1}_{yi}"
        points = [0, 0, 0, W1, H1, W1, H1, 0]
        self.PlacementDB.append(block_name)
        moduleName = "cbx_1__0_" if yi == 0 else "cbx_1__2_" if yi == self.sizeY else "cbx_1__1_"
        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly, llx+W1, lly+H1],
                                           "points": points,
                                           "center": [llx+W1*0.5, lly+H1*0.5],
                                           "module": moduleName,
                                           "color": self.CBX_COLOR,
                                           "shape": [(llx, lly, W1, H1)],
                                           "initShape": initShape,
                                           "xi": xi,
                                           "yi": yi}

    def add_cby(self, xi, yi, lbl=None):
        x, y = (xi+1)*self.CLB_GRID_X, (yi+1)*self.CLB_GRID_Y
        llx = x-self.snapDims((self.CLB_W*0.5)+self.CBY_W)
        lly = y-self.snapDims(self.CBY_H)*0.5
        W1 = self.CBY_W
        H1 = self.CBY_H
        initShape = [(llx, lly, W1, H1)]

        if not self.skipChannels:
            llx += self.CBY_CHAN_L
            lly += self.CBY_CHAN_B
            W1 = self.CBY_W-self.CBY_CHAN_L-self.CBY_CHAN_R
            H1 = self.CBY_H-self.CBY_CHAN_T-self.CBY_CHAN_B

        block_name = f"cby_{xi}__{yi+1}_"
        short_block_name = f"CY_{xi}_{yi+1}"
        points = [0, 0, 0, W1, H1, W1, H1, 0]
        self.PlacementDB.append(block_name)
        moduleName = "cby_0__1_" if xi == 0 else "cby_2__1_" if xi == self.sizeY else "cby_1__1_"
        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly, llx+W1, lly+H1],
                                           "points": points,
                                           "center": [llx+W1*0.5, lly+H1*0.5],
                                           "module": moduleName,
                                           "color": self.CBY_COLOR,
                                           "shape": [(llx, lly, W1, H1)],
                                           "initShape": initShape,
                                           "xi": xi,
                                           "yi": yi}

    def get_stype(self, x, y):
        if x == 0:
            if y == 0:
                return 1
            elif y == self.sizeX:
                return 3
            else:
                return 2
        elif x == self.sizeY:
            if y == 0:
                return 7
            elif y == self.sizeX:
                return 5
            else:
                return 6
        else:
            if y == 0:
                return 8
            elif y == self.sizeX:
                return 4
            else:
                return 0

    def unique(self, sequence):
        seen = set()
        u = [x for x in sequence if not (x in seen or seen.add(x))]
        return [val for sublist in u for val in sublist]

    def add_sb(self, xi, yi):
        '''
                   d
                 +----+
               c |    |
             b   |    |   e
            +----+    +----+
          a |              |           Cross Shape
            |              |           -lengths {a b c d e f}
            +----+    +----+
                 |    |
                 |    | f
                 +----+
        '''
        x = xi*self.CLB_GRID_X
        y = yi*self.CLB_GRID_Y

        llxB1 = x+(0.5*self.CLB_W)
        llyB1 = y+(self.CBY_H*0.5)
        WidthB1 = self.SIDE_X
        HeightB1 = self.SB_H

        llxB2 = x + (self.CBX_W*0.5)
        llyB2 = y + (self.CLB_H*0.5)
        WidthB2 = self.SB_W
        HeightB2 = self.SIDE_Y

        a = self.SIDE_Y
        b = e = (WidthB2-self.SIDE_X) * 0.5
        c = f = (HeightB1-self.SIDE_Y)*0.5
        d = self.SIDE_X

        Stype = self.get_stype(xi, yi)
        if Stype == 1:  # SB_0__0_
            llyB1 += c
            HeightB1 += -c
            llxB2 += b
            WidthB2 += -b
            b = f = 0
        elif Stype == 2:  # SB_0__1_
            llxB2 += b
            WidthB2 -= b
            b = 0
        elif Stype == 3:  # SB_0__2_
            llxB2 += b
            WidthB2 -= b
            HeightB1 -= f
            c = b = 0
        elif Stype == 4:  # SB_1__2_
            HeightB1 -= c
            c = 0
        elif Stype == 5:  # SB_2__2_
            HeightB1 -= c
            WidthB2 -= e
            c = e = 0
        elif Stype == 6:  # SB_2__1_
            WidthB2 -= e
            e = 0
        elif Stype == 7:  # SB_2__0_
            llyB1 += f
            HeightB1 -= f
            WidthB2 -= e
            e = f = 0
        elif Stype == 8:  # SB_1__0_
            llyB1 += f
            HeightB1 -= f
            f = 0

        block_name = f"sb_{xi}__{yi}_"
        short_block_name = f"SB_{xi}_{yi}"
        initShape = [(llxB1, llyB1, WidthB1, HeightB1),
                     (llxB2, llyB2, WidthB2, HeightB2)]
        points = self.unique([(b, 0), (b, f),
                              (0, f), (0, (f+a)),
                              (b, (f+a)), (b, (a+c+f)),
                              ((b+d), (a+c+f)), ((b+d), (a+f)),
                              ((b+d+e), (a+f)), ((b+d+e), f),
                              ((b+d), f), ((b+d), 0)])
        self.PlacementDB.append(block_name)
        moduleNames = [
            "sb_1__1_", "sb_0__0_", "sb_0__1_",
            "sb_0__2_", "sb_1__2_", "sb_2__2_",
            "sb_2__1_", "sb_2__0_", "sb_1__0_",
        ]

        llx = min([i[0] for i in initShape])
        lly = min([i[1] for i in initShape])
        if Stype == 1:
            print(initShape)
        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly, llx+f+a+c, lly+b+d+e],
                                           "points": points,
                                           "center": [llx+(WidthB1*0.5)+b,
                                                      lly+(HeightB2*0.5)+f],
                                           "module": moduleNames[Stype],
                                           "color": self.SB_COLOR,
                                           "shape": initShape,
                                           "xi": xi,
                                           "yi": yi,
                                           "dims": [a, b, c, d, e, f],
                                           "initShape": initShape}

    def add_gridIOH(self, xi, yi, side, lbl=None):
        x, y = (xi+1)*self.CLB_GRID_X, (yi+1)*self.CLB_GRID_Y
        llx = x-self.snapDims((self.GRID_IOH_W)*0.5)
        lly = y-self.snapDims((self.CLB_H*0.5)+self.CBX_H)
        lly += (-1*self.gridIO_HB) if side == "bottom" else self.CBX_H
        W1 = self.GRID_IOH_W
        H1 = self.gridIO_HB
        initShape = [(llx, lly, W1, H1)]

        if not self.skipChannels:
            llx += self.CBX_CHAN_L
            lly += 0 if side == "bottom" else self.gridIO_MT
            W1 = self.GRID_IOH_W-self.CBX_CHAN_L-self.CBX_CHAN_R
            H1 = self.gridIO_HB-self.gridIO_MB

        if side == "bottom":
            moduleName = "grid_io_bottom_bottom"
            block_name = f"grid_io_{side}_{side}_{xi+1}__{yi}_"
            short_block_name = f"io{side}_{xi+1}_{yi}"
        else:
            moduleName = "grid_io_top_top"
            block_name = f"grid_io_{side}_{side}_{xi+1}__{yi+1}_"
            short_block_name = f"io{side}_{xi+1}_{yi+1}"
        points = [0, 0, 0, W1, H1, W1, H1, 0]
        self.PlacementDB.append(block_name)

        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly, llx+W1, lly+H1],
                                           "points": points,
                                           "center": [llx+W1*0.5, lly+H1*0.5],
                                           "module": moduleName,
                                           "color": self.GRID_IO_COLOR,
                                           "shape": [(llx, lly, W1, H1)],
                                           "initShape": initShape}

    def add_gridIOV(self, xi, yi, side, lbl=None):
        x, y = (xi+1)*self.CLB_GRID_X, (yi+1)*self.CLB_GRID_Y
        llx = x-self.snapDims((self.CLB_W*0.5)+self.CBY_W)
        lly = y-self.snapDims(self.GRID_IOV_H)*0.5
        llx += (-1*(self.gridIO_WL)) if side == "left" else self.CBY_W
        W1 = self.gridIO_WL
        H1 = self.GRID_IOV_H
        initShape = [(llx, lly, W1, H1)]

        if not self.skipChannels:
            llx += self.CBY_CHAN_L
            llx += (-1*self.gridIO_ML) if side == "left" else self.gridIO_MR
            lly += self.CBY_CHAN_B
            W1 = self.gridIO_WL-self.gridIO_ML
            H1 = self.GRID_IOV_H-self.CBY_CHAN_T-self.CBY_CHAN_B

        if side == "left":
            block_name = f"grid_io_{side}_{side}_{xi}__{yi+1}_"
            short_block_name = f"io{side}_{xi}_{yi+1}"
            moduleName = "grid_io_left_left"
        else:
            block_name = f"grid_io_{side}_{side}_{xi+1}__{yi+1}_"
            short_block_name = f"io{side}_{xi+1}_{yi+1}"
            moduleName = "grid_io_right_right"
        points = [0, 0, 0, W1, H1, W1, H1, 0]
        self.PlacementDB.append(block_name)

        self.PlacementDBKey[block_name] = {"name": block_name,
                                           "short_name": short_block_name,
                                           "bbox": [llx, lly, llx+W1, lly+H1],
                                           "points": points,
                                           "center": [llx+W1*0.5, lly+H1*0.5],
                                           "module": moduleName,
                                           "color": self.GRID_IO_COLOR,
                                           "shape": [(llx, lly, W1, H1)],
                                           "initShape": initShape}

    def add_pad(self, side="L", number=0, padname="xx"):
        CoreMinX, CoreMinY = (0.5*self.CLB_W), (0.5*self.CLB_H)
        CoreMaxX, CoreMaxY = (((self.sizeX+0.5) * self.CLB_GRID_X)+0.5*self.CBY_W,
                              ((self.sizeY+0.5) * self.CLB_GRID_Y)+0.5*self.CBX_H)
        if side in ["L", "R"]:
            pad_w = self.pad_w
            pad_h = (((self.CLB_H+self.CBX_H)*self.sizeY+1) +
                     self.CBX_H)/self.NumOfPads
            shift = (number*pad_h)
            initialshitX = (self.CLB_GRID_Y - self.CBX_H-(self.CLB_H*0.5))
            initialshitY = (self.CLB_GRID_X - self.CBY_W-(self.CLB_W*0.5))
            pad_spacing = 24
            if side == "L":
                pad_x = CoreMinX - (pad_w*0.5) - pad_spacing
                pad_y = initialshitX + shift + pad_h*0.5
                pad_llx = pad_x - (pad_w*0.5)
                pad_lly = pad_y - (pad_h*0.5)
                pad_w, pad_h = pad_w, pad_h
                rot = 0
                t = 0.5
            elif side == "R":
                pad_x = CoreMaxX + (pad_w*0.5) + pad_spacing
                pad_y = initialshitX + shift + pad_h*0.5
                pad_llx = pad_x - (pad_w*0.5)
                pad_lly = pad_y - (pad_h*0.5)
                pad_w, pad_h = pad_w, pad_h
                rot = 0
                t = 0.5
        else:
            pad_w = (((self.CLB_W+self.CBY_W)*self.sizeX+1) +
                     self.CBY_W)/self.NumOfPads
            pad_h = self.pad_h
            shift = (number*pad_w)
            initialshitY = (self.CLB_GRID_X - self.CBY_W-(self.CLB_W*0.5))
            pad_spacing = 3
            if side == "T":
                pad_x = initialshitY + shift + pad_w*0.5
                pad_y = CoreMaxY + pad_spacing + pad_h*0.5
                pad_llx = pad_x - (0.5*pad_w)
                pad_lly = pad_y - pad_h*0.5
                pad_w, pad_h = pad_w, pad_h
                rot = 90
                t = 0.5
            elif side == "B":
                pad_x = initialshitY + shift + pad_w*0.5
                pad_y = CoreMinY - pad_spacing - pad_h*0.5
                pad_llx = pad_x - (0.5*pad_w)
                pad_lly = pad_y - pad_h*0.5
                pad_w, pad_h = pad_w, pad_h
                rot = -90
                t = 0.5

        self.GPIOPlacmentKey.append(
            {
                "side": side,
                "rot": rot,
                "text": padname.strip(),
                "shape": [(pad_llx, pad_lly, pad_w, pad_h)],
                "color": self.PAD_COLOR,
                "center": [pad_x, pad_y],
            }
        )

    def moduleFmt(self, mod, X, Y):
        return f"{mod}_{X}__{Y}_"