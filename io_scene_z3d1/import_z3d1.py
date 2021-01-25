# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Created by Dummiesman, 2021
# Based on source code from ZModeler 2 by Oleg M.
#
# ##### END LICENSE BLOCK #####

import bpy, bmesh, mathutils
import time, struct, io, math, os
import zlib
from bpy_extras.io_utils import axis_conversion

import io_scene_z3d1.z3d1_chunktypes as chunktypes
import io_scene_z3d1.z3d1_chunkflags as chunkflags
import io_scene_z3d1.z3d1_flags as z3dflags
from io_scene_z3d1.z3d1_classes import *

# GLOBALS
# texture_paths : directories to search for textures
# texture_names : texture file names
# texture_id_map : key is a texture_name, value is a blender ID for the texture (key may not exist)
# object_id_map : key is a object name, value is a blender ID for the object
# meshes_desc : meshes_desc structure from Z3D
# material_desc : material_desc structure from Z3D
# material_id_map : key is a material ID from Z3D, value is a blender ID

global texture_paths
texture_paths = []

global texture_names
texture_names = []

global texture_id_map
texture_id_map = {}

global material_id_map 
material_id_map = {}

global object_id_map
object_id_map = {}

global meshes_desc
meshes_desc = tDescData(None)

global material_desc
material_desc = tMaterialData(None)


######################################################
# HELPERS
######################################################
def try_load_texture(texture_name, z3d_directory):
    global texture_id_map
    
    # search in the texture_paths
    for path in texture_paths:
        fullpath = path + texture_name
        if os.path.exists(fullpath):
            img = bpy.data.images.load(fullpath)
            texture_id_map[texture_name] = img.name
            return
        
    # else search in local folder
    local_path = os.path.join(z3d_directory, texture_name)
    if os.path.exists(local_path):
        img = bpy.data.images.load(local_path)
        texture_id_map[texture_name] = img.name

def read_zstring(file, size=-1):
    if size < 0:
        size = struct.unpack('<L', file.read(4))[0]
    if size == 0:
        return ""
        
    str_bytes = bytearray(file.read(size - 1))
    file.seek(1, 1) # seek past null terminator

    return str_bytes.decode("utf-8", "replace")

def read_zstring_noterminator(file, size = -1):
    if size < 0:
        size = struct.unpack('<L', file.read(4))[0]
    if size == 0:
        return ""
    
    str_bytes = bytearray(file.read(size))
    return str_bytes.decode("utf-8", "replace")
     

def read_name_chunk(file):
    chunk_type, chunk_size = struct.unpack('<LL', file.read(8))
    if chunk_type != chunktypes.Z3D_CHUNK_NAME:
        raise Exception("read_name_chunk chunk_type was wrong, got " + str(chunk_type))
    return read_zstring(file, chunk_size)


######################################################
# IMPORT MAIN FILES
######################################################
def import_material(file, chunk_size):
    global material_desc
    global material_id_map
    global texture_id_map
    
    material_name = read_name_chunk(file)
    
    # read d3d material and params
    material = None
    params = None
    
    if material_desc.n_flags & chunkflags.CHUNK_MAT_FLAGS_HASMATREC:
        material = D3DMATERIAL7(file)
    else:
        material = material_desc.material
    
    if material_desc.n_flags & chunkflags.CHUNK_MAT_FLAGS_HASPARAMS:
        params = MATERIALPARAMS(file)
    else:
        params = material_desc.params
    
    # read textures
    prim_texture = None
    refl_texture = None
    bump_texture = None
    rsrv_texture = None
    if params.prim_texture != -1:
        prim_texture = read_name_chunk(file)
    if params.refl_texture != -1:
        refl_texture = read_name_chunk(file)
    if params.bump_texture != -1:
        bump_texture = read_name_chunk(file)
    if params.rsrv_texture != -1:
        rsrv_texture = read_name_chunk(file)
        
    # actually make the material
    mtl = bpy.data.materials.new(name=material_name)
    material_id_map[len(material_id_map)] = mtl.name
    
    mtl.use_nodes = True
    mtl.use_backface_culling = True
    
    # setup colors
    bsdf = mtl.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = material.diffuse_color
    bsdf.inputs['Emission'].default_value = material.emissive_color
    bsdf.inputs['Specular'].default_value = material.power / 100.0
    bsdf.inputs['Roughness'].default_value = 0
    bsdf.inputs['Alpha'].default_value = material.diffuse_color[3]

    mtl.diffuse_color = material.diffuse_color
    mtl.specular_intensity = 0.1
    mtl.metallic = material.power
    
    # set alpha mode
    if params.alpha_treat == 2:
        mtl.blend_method = 'CLIP'
        mtl.alpha_threshold = params.alpha_ref / 255
    elif params.alpha_treat == 1:
        # uh oh, most materials have this, so BLEND looks horrible
        mtl.blend_method = 'HASHED' 
        
    # setup textures
    if prim_texture in texture_id_map:
        tex_result = bpy.data.images[texture_id_map[prim_texture]]
        
        tex_image_node = mtl.node_tree.nodes.new('ShaderNodeTexImage')
        tex_image_node.image = tex_result
        tex_image_node.location = mathutils.Vector((-640.0, 20.0))
        
        mtl.node_tree.links.new(bsdf.inputs['Base Color'], tex_image_node.outputs['Color'])
        mtl.node_tree.links.new(bsdf.inputs['Alpha'], tex_image_node.outputs['Alpha'])


def import_splines(file):
    # create a Blender object and link it
    scn = bpy.context.scene

    me = bpy.data.meshes.new('Splines_Mesh')
    ob = bpy.data.objects.new('Splines', me)
    
    scn.collection.objects.link(ob)
    
    spline_count, vertex_count = struct.unpack('<LL', file.read(8))
    spline_verts = []
    
    for i in range(vertex_count):
        x, z, y = struct.unpack('<fff', file.read(12))
        x *= -1.0
        spline_verts.append((x, y, z))


def import_object(file, chunk_size):
    global meshes_desc
    global object_id_map
    
    # get read start pos
    chunk_start = file.tell()
    chunk_end = chunk_start + chunk_size
    
    # read object name
    obj_name = read_name_chunk(file)
    
    # ignore UV data
    if obj_name == "UVMapperDATA":
        file.seek(chunk_end, 0)
        return
    
    # create a Blender object and link it
    scn = bpy.context.scene

    me = bpy.data.meshes.new(obj_name + '_Mesh')
    ob = bpy.data.objects.new(obj_name, me)
    object_id_map[obj_name] = ob.name

    bm = bmesh.new()
    bm.from_mesh(me)
    
    scn.collection.objects.link(ob)
    
    # create layers for this object
    uv_layer = bm.loops.layers.uv.new()
    
    # materials remapping
    ob_material_remap = {}
    
    # get flags and misc
    flags = meshes_desc.misc_f[0]
    misc = [meshes_desc.misc_f[1], meshes_desc.misc_f[2], meshes_desc.misc_f[3], meshes_desc.misc_f[4]]
    
    if meshes_desc.n_flags & chunkflags.CHUNK_FLAGS_HASFLAGS:
        flags = struct.unpack('<L', file.read(4))[0]
        
    for i in range(4):
        if meshes_desc.n_flags & (chunkflags.CHUNK_FLAGS_HASMISCV0 << i):
            misc[i] = struct.unpack('<L', file.read(4))[0]
    
    # apply flags    
    ob.hide_set((flags & z3dflags.Z3D_FLAG_HIDDEN) != 0)
    ob.select_set((flags & z3dflags.Z3D_FLAG_SELECTED) != 0)
    
    # start reading subchunks 
    read_subchunk = True
    
    has_face_desc = False
    has_vert_desc = False
    vert_desc = None
    face_desc = None
    
    vert_buf_size = 0
    
    while read_subchunk:
        chunk_type, chunk_size = struct.unpack('<LL', file.read(8))
        if chunk_type == chunktypes.Z3D_CHUNK_VERTTABLE_DESC:
            print("  Z3D_CHUNK_VERTTABLE_DESC")
            has_vert_desc = True
            vert_desc = tDescData(file)
        elif chunk_type == chunktypes.Z3D_CHUNK_FACETABLE_DESC:
            print("  Z3D_CHUNK_FACETABLE_DESC")
            has_face_desc = True
            face_desc = tFaceDescData(file)
        elif chunk_type == chunktypes.Z3D_CHUNK_OBJECT_LOCALMATRIX:
            print("  Z3D_CHUNK_OBJECT_LOCALMATRIX")
            matrix = struct.unpack('<ffffffffffffffff', file.read(64))
            col1 = (matrix[0], matrix[1], matrix[2], matrix[3])
            col2 = (matrix[4], matrix[5], matrix[6], matrix[7])
            col3 = (matrix[8], matrix[9], matrix[10], matrix[11])
            col4 = (matrix[12], matrix[13], matrix[14], matrix[15])

            # create matrix, and convert its coordinate space
            mtx = mathutils.Matrix((col1, col2, col3, col4))
            mtx.transpose()
            
            # convert matrix to Blender Z up
            mat_rot = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
            mtx_convert = axis_conversion(from_forward='Z', 
                from_up='Y',
                to_forward='-Y',
                to_up='Z').to_4x4()
            
            mtx = mtx_convert @ mtx
            mtx @= mat_rot
            
            # fix broken matrix
            # basically some matrices that should be identity
            # come in with really weird rotation, and -1 -1 -1 scale
            # and afaik ZM1 provides no way to scale the local matrix
            # so this should be a safe way to check
            loc, rot, sca = mtx.decompose()
            if sca[0] < 0 and sca[1] < 0 and sca[2] < 0:
                mtx.identity()

            # calculate inverse
            mtx_inv = mtx.inverted_safe()
            
            # set object transform
            ob.matrix_basis = mtx
            
            # reverse transform vertices
            for vert in bm.verts:
                vert.co =  mtx_inv @ vert.co
    
        elif chunk_type == chunktypes.Z3D_CHUNK_VERTTABLE_DATA:
            print("  Z3D_CHUNK_VERTTABLE_DATA")
            if has_vert_desc:
                vt_flags = vert_desc.misc_f[0]
                vt_misc = [vert_desc.misc_f[1], vert_desc.misc_f[2], vert_desc.misc_f[3], vert_desc.misc_f[4]]
                
                num_verts = vert_desc.num
                vert_buf_size += num_verts
                
                for i in range(num_verts):
                    vx, vz, vy = struct.unpack('<fff', file.read(12))
                    nx, nz, ny = struct.unpack('<fff', file.read(12))
                    
                    vy *= -1.0
                    ny *= -1.0
                    
                    # status
                    if vert_desc.n_flags & chunkflags.CHUNK_FLAGS_HASFLAGS:
                        vt_flags = struct.unpack('<L', file.read(4))[0]
                    else:
                        vt_flags = vert_desc.misc_f[0]
                        
                    for i in range(4):
                        if vert_desc.n_flags & (chunkflags.CHUNK_FLAGS_HASMISCV0 << i):
                            vt_misc[i] = struct.unpack('<L', file.read(4))[0]
                        else:
                            vt_misc[i] = vert_desc.misc_f[i+1]
                            
                    # create the actual vert
                    vert = bm.verts.new((vx, vy, vz))
                    
                    # apply flags
                    if vt_flags & z3dflags.Z3D_FLAG_SELECTED:
                        vert.select = True
                    if vt_flags & z3dflags.Z3D_FLAG_HIDDEN:
                        vert.hide = True
                    
                bm.verts.ensure_lookup_table()
            else:
                print("VERTTABLE_DATA present before VERTTABLE_DESC, skipping this chunk")
                file.seek(chunk_size, 1)

        elif chunk_type == chunktypes.Z3D_CHUNK_FACETABLE_DATA:
            print("  Z3D_CHUNK_FACETABLE_DATA")
            if has_face_desc:
                ft_flags = face_desc.misc_f[0]
                ft_misc = [face_desc.misc_f[1], face_desc.misc_f[2], face_desc.misc_f[3], face_desc.misc_f[4]]
                face_render_flags = [face_desc.n_render_flags, 0, 0]
                face_uv = [face_desc.u1, face_desc.u2, face_desc.u3, face_desc.v1, face_desc.v2, face_desc.v3]
                face_material = face_desc.material
                
                num_faces = face_desc.num
                
                face_struct = None
                face_struct_size = 0
                if vert_buf_size <= 0x100:
                    face_struct = '<BBB'
                    face_struct_size = 3
                elif vert_buf_size <= 0x10000:
                    face_struct = '<HHH'
                    face_struct_size = 6
                else:
                    face_struct = '<LLL'
                    face_struct_size = 12
                
                
                for i in range(num_faces):
                    index2, index1, index0 = struct.unpack(face_struct, file.read(face_struct_size))
                    rec_flags = struct.unpack('<L', file.read(4))[0]
                    
                    # status
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASFLAGS:
                        ft_flags = struct.unpack('<L', file.read(4))[0]
                    else:
                        ft_flags = face_desc.misc_f[0]
                        
                    for i in range(4):
                        if rec_flags & (chunkflags.CHUNK_FLAGS_HASMISCV0 << i):
                            ft_misc[i] = struct.unpack('<L', file.read(4))[0]
                        else:
                            ft_misc[i] = face_desc.misc_f[i+1]
                            
                    # other
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASMATERIAL:
                        face_material = struct.unpack('<L', file.read(4))[0]
                    else:
                        face_material = face_desc.material
                    
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASRENDERFLAGS:
                        face_render_flags_tmp = struct.unpack('<LLL', file.read(12))
                        face_render_flags[0] = face_render_flags_tmp[0]
                        face_render_flags[1] = face_render_flags_tmp[1]
                        face_render_flags[2] = face_render_flags_tmp[2]
                    else:
                        face_render_flags[0] = face_desc.n_render_flags
                        
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASPAIR:
                        file.seek(4, 1) # unused
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASRESERVFLAGS:
                        file.seek(12, 1) # unused    
                    if rec_flags & chunkflags.CHUNK_FLAGS_HASUV:
                        face_uv_tmp = struct.unpack('<ffffff', file.read(24))
                        face_uv = [face_uv_tmp[0], face_uv_tmp[1], face_uv_tmp[2], face_uv_tmp[3], face_uv_tmp[4], face_uv_tmp[5]]
                    else:
                        face_uv = [face_desc.u1, face_desc.u2, face_desc.u3, face_desc.v1, face_desc.v2, face_desc.v3]
                     
                    # create the actual face
                    try:
                        vert0 = bm.verts[index0]
                        vert1 = bm.verts[index1]
                        vert2 = bm.verts[index2]
                        
                        face = bm.faces.new((vert0, vert1, vert2))
                        face.smooth = True
                        
                        # set uvs
                        face.loops[2][uv_layer].uv = (face_uv[0], 1 - face_uv[3])
                        face.loops[1][uv_layer].uv = (face_uv[1], 1 - face_uv[4])
                        face.loops[0][uv_layer].uv = (face_uv[2], 1 - face_uv[5])
                        
                        # apply flags
                        # for some reason vert.hide isn't working so we hide the face as a workaround...
                        if ft_flags & z3dflags.Z3D_FLAG_SELECTED:
                            face.select = True
                        if ft_flags & z3dflags.Z3D_FLAG_HIDDEN or (vert0.hide or vert1.hide or vert2.hide):
                            face.hide = True
                        
                        # assign material
                        face_material_remapped = -1
                        real_material_index = face_material
                        
                        if face_material in ob_material_remap:
                            face_material_remapped = ob_material_remap[face_material]
                        elif real_material_index in material_id_map:
                            real_material_name = material_id_map[real_material_index]
                            
                            real_material = bpy.data.materials.get(real_material_name)
                            ob.data.materials.append(real_material)
                            
                            ob_material_remap[face_material] = len(ob.data.materials) - 1
                            face_material_remapped = len(ob.data.materials) - 1
                            
                        if face_material_remapped >= 0:
                            face.material_index = face_material_remapped
                    except Exception as e:
                        print("Failed to create face: " + str(e))
            else:
                print("FACETABLE_DATA present before FACETABLE_DESC, skipping this chunk")
                file.seek(chunk_size, 1)
        else:
            print("  END, found unneeded chunk (" + str(chunk_type) + ")")
            read_subchunk = False
        
        if file.tell() >= chunk_end:
            break
    
    # calculate normals
    bm.normal_update()
    
    # free resources
    bm.to_mesh(me)
    bm.free()
    
    # seek to end of this chunk, sometimes we break because
    # we found data we can't read / don't want
    file.seek(chunk_end, 0)


def import_hierarchy(file):
    global object_id_map
    
    while True:
        parent_name = read_zstring_noterminator(file)
        child_name = read_zstring_noterminator(file)
        
        total_len = len(parent_name) + len(child_name)
        if total_len == 0:
            break
            
        if len(parent_name) > 0 and len(child_name) > 0:
            if parent_name in object_id_map and child_name in object_id_map:
                parent_obj = bpy.data.objects[object_id_map[parent_name]]
                child_obj = bpy.data.objects[object_id_map[child_name]]
                
                child_obj.parent = parent_obj
        
        
######################################################
# IMPORT
######################################################
def load_z3d1(filepath,
             context):

    print("importing Z3D v1.x: %r..." % (filepath))

    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')

    time1 = time.clock()
    file = open(filepath, 'rb')
    
    file_dir = os.path.dirname(filepath)
    
    # reset globals
    global texture_paths
    texture_paths = []

    global texture_names
    texture_names = []

    global texture_id_map
    texture_id_map = {}

    global material_id_map 
    material_id_map = {}

    global object_id_map
    object_id_map = {}
    
    global meshes_desc
    meshes_desc = tDescData(None)

    global material_desc
    material_desc = tMaterialData(None)
    
    # get size
    file.seek(0, 2)
    fsize = file.tell()
    file.seek(0, 0)
    
    if fsize < 12:
        file.close()
        raise Exception("Not a ZModeler 1.x version Z3D file.")
    
    # get header
    magic, flags, length = struct.unpack('<LLL', file.read(12))
    is_compressed = flags & 0x0001
    
    if magic != 0x4D44335A:
        file.close()
        raise Exception("Not a ZModeler 1.x version Z3D file.")
    
    if length <= 0:
        file.close()
        return
        
    # decompress if needed
    if is_compressed:
        file_data = file.read(fsize - 12)
        decompressed_data = zlib.decompress(file_data)

        # re-open file on our new bytes obj
        file.close()
        file = io.BytesIO(decompressed_data)
        
        # reset filesize
        fsize = length
        
        
    # start reading our z3d file
    while file.tell() < fsize:
        chunk_start = file.tell()
        chunk_type, chunk_size = struct.unpack('<LL', file.read(8))
        chunk_end = chunk_start + chunk_size + 8
        
        if chunk_type == chunktypes.Z3D_CHUNK_TEXTUREPATH:
            print("Z3D_CHUNK_TEXTUREPATH")
            texture_path = read_zstring(file, chunk_size)
            texture_paths.append(texture_path)
        elif chunk_type == chunktypes.Z3D_CHUNK_TEXTURENAME:
            print("Z3D_CHUNK_TEXTURENAME")  
            texture_name = read_zstring(file, chunk_size)
            texture_names.append(texture_name)
            try_load_texture(texture_name, file_dir)
        elif chunk_type == chunktypes.Z3D_CHUNK_MESHES_DESC:
            print("Z3D_CHUNK_MESHES_DESC")
            meshes_desc = tDescData(file)
        elif chunk_type == chunktypes.Z3D_CHUNK_MATERIALS_DESC:
            print("Z3D_CHUNK_MATERIALS_DESC")
            material_desc = tMaterialData(file)
            material_desc.ambient = (0, 0, 0, 0)
        elif chunk_type == chunktypes.Z3D_CHUNK_MATERIAL:
            print("Z3D_CHUNK_MATERIAL")
            import_material(file, chunk_size)
        elif chunk_type == chunktypes.Z3D_CHUNK_OBJECT:
            print("Z3D_CHUNK_OBJECT")
            import_object(file, chunk_size)
        elif chunk_type == chunktypes.Z3D_CHUNK_HIERARCHY:
            print("Z3D_CHUNK_HIERARCHY")
            import_hierarchy(file)
        elif chunk_type == chunktypes.Z3D_CHUNK_UNRECOGNIZEDDATA:
            print("Z3D_CHUNK_UNRECOGNIZEDDATA")
            file.seek(chunk_size, 1)
        elif chunk_type == 0xF0E00F0E or chunk_type == 0:
            # EOF, break 
            break
        else:
            print("Unknown chunk at " + str(chunk_start) + " (you can probably ignore this)")
            print("Chunk_type:" + str(chunk_type) + ", Chunk_size:" + str(chunk_size))
            file.seek(chunk_size, 1)
        
    print(" read " + str(file.tell()) + " of " + str(fsize))
    print(" done in %.4f sec." % (time.clock() - time1))
    
    file.close()


def load(operator,
         context,
         filepath="",
         ):

    load_z3d1(filepath,
             context,
             )

    return {'FINISHED'}
