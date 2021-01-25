import struct


class tFaceDescData:
    def __init__(self, file):
        num, n_flags = struct.unpack('<LL', file.read(8))
        self.num = num
        self.n_flags = n_flags
        self.misc_f = struct.unpack('<LLLLL', file.read(20))
        self.material = struct.unpack('<L', file.read(4))[0]
        
        u1, u2, u3, v1, v2, v3 = struct.unpack('<ffffff', file.read(24))
        self.u1 = u1
        self.u2 = u2
        self.u3 = u3
        self.v1 = v1
        self.v2 = v2
        self.v3 = v3
        
        self.pair_index = struct.unpack('<L', file.read(4))[0]
        
        n_render_flags, n_blend_flags, n_wrap_flags, reserv1, reserv2, reserv3 = struct.unpack('<LLLLLL', file.read(24))
        self.n_render_flags = n_render_flags
        self.n_blend_flags = n_blend_flags
        self.n_wrap_flags = n_wrap_flags


class tDescData:
    def __init__(self, file):
        if file is not None:
            num, n_flags = struct.unpack('<LL', file.read(8))
            self.num = num
            self.n_flags = n_flags
            self.misc_f = struct.unpack('<LLLLL', file.read(20))
        else:
            self.num = 0
            self.n_flags = 0
            self.misc_f = [0, 0, 0, 0, 0]


class D3DMATERIAL7:
    def __init__(self, file):
        if file is not None:
            self.diffuse_color = struct.unpack('<ffff', file.read(16))
            self.ambient_color = struct.unpack('<ffff', file.read(16))
            self.specular_color = struct.unpack('<ffff', file.read(16))
            self.emissive_color = struct.unpack('<ffff', file.read(16))
            self.power = struct.unpack('<f', file.read(4))[0]
        else:
            self.diffuse_color = (0.0, 0.0, 0.0, 0.0)
            self.ambient_color = (0.0, 0.0, 0.0, 0.0)
            self.specular_color = (0.0, 0.0, 0.0, 0.0)
            self.emissive_color = (0.0, 0.0, 0.0, 0.0)
            self.power = 0.0


class MATERIALPARAMS:
    def __init__(self, file):
        if file is not None:
            prim_texture, bump_texture, refl_texture, rsrv_texture = struct.unpack('<llll', file.read(16))
            self.prim_texture = prim_texture
            self.bump_texture = bump_texture
            self.refl_texture = refl_texture
            self.rsrv_texture = rsrv_texture
            
            self.shine = struct.unpack('<f', file.read(4))[0]
            prim_apply, bump_apply, refl_apply, rsrv_apply = struct.unpack('<LLLL', file.read(16))
            self.prim_apply = prim_apply
            self.bump_apply = bump_apply
            self.refl_apply = refl_apply
            self.rsrv_apply = rsrv_apply
            
            src_blend, dst_blend = struct.unpack('<LL', file.read(8))
            self.src_blend = src_blend
            self.dst_blend = dst_blend
            
            alpha_treat, alpha_ref, alpha_func, unused = struct.unpack('<BBBB', file.read(4))
            self.alpha_treat = alpha_treat
            self.alpha_ref = alpha_ref
            self.alpha_func = alpha_func
            
            color_key_low, color_key_high = struct.unpack('<LL', file.read(8))
            self.color_key_low = color_key_low
            self.color_key_high = color_key_high
        else:
            self.prim_texture = -1
            self.bump_texture = -1
            self.refl_texture = -1
            self.rsrv_texture = -1
            
            self.shine = 0.0
            self.prim_apply = 0
            self.bump_apply = 0
            self.refl_apply = 0
            self.rsrv_apply = 0
            
            self.src_blend = 0
            self.dst_blend = 0
            
            self.alpha_treat = 0
            self.alpha_ref = 0
            self.alpha_func = 0
            
            self.color_key_low = 0
            self.color_key_high = 0


class tMaterialData:
    def __init__(self, file):
        # read header
        if file is not None:
            num, n_flags = struct.unpack('<LL', file.read(8))
            self.num = num
            self.n_flags = n_flags
        else:
            self.num = 0
            self.n_flags = 0
        
        # material
        self.material = D3DMATERIAL7(file)
        
        # params
        self.params = MATERIALPARAMS(file)
