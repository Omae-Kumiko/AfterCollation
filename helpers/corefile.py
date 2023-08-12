from __future__ import annotations

import re
from typing import Any
from pathlib import Path
from logging import Logger
from multiprocessing import Pool

from utils import *
from configs import *
from .formatter import *
import helpers.season as hs

import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pymediainfo import Track


__all__ = [
    'CF',
    'CoreFile',
    'toCoreFiles',
    'toCoreFilesWithTqdm',
    ]




class CoreFile:

    '''
    CoreFile is a wrapper over MediaInfo, providing easier access to mediainfo.
    A `core file` means it's one in `VNx_ALL_EXTS` (MKV/MKA/MP4/FLAC/PNG/ASS/7Z/ZIP/RAR)
    i.e. the core part of files in a BDRip (as opposed to CDs/Scans).

    VideoNaming tools depends on this class.
    '''

    def __init__(
        self,
        path: Path|str,
        season: hs.Season|None = None,
        depends: CoreFile|None = None,
        init_crc32: bool = False,
        init_audio_samples: bool = False,
        logger: Logger|None = None,
        ) -> None:

        if not (path := Path(path).resolve()).is_file():
            raise FileNotFoundError(f'The file "{self.path}" is missing to init CoreFile instance.')
        self.__path: Path = path

        # once the path is validated, init mediainfo
        self.__mediainfo: MediaInfo = getMediaInfo(path)

        self.__season: hs.Season|None = season
        if season:  # hook each other
            season.add(self, hook=True)  # dont hook here as this CoreFile has not been init - hook will fail
            # self.__season = season

        self.__depends: CoreFile|None = depends

        self.__crc32: str = ''
        if init_crc32:
            self.__crc32 = getCRC32(self.path, prefix='', pass_not_found=False) if init_crc32 else ''

        self.__audio_samples: str = ''
        if init_audio_samples and self.has_audio and ENABLE_AUDIO_SAMPLES_IN_VNA:
            self.__audio_samples = pickAudioSamples(self.path)

        self.__logger: Logger|None = logger

        self.__qlabel: str|None = None
        self.__tlabel: str|None = None

        # attach the naming fields of variable names to this instance
        for v in COREFILE_DICT.values():
            setattr(self, v, '')

    #* built-in methods override ---------------------------------------------------------------------------------------

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.__mediainfo, __name)

    def __getstate__(self) -> dict:
        return self.__dict__

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    #* access init parameters ------------------------------------------------------------------------------------------

    @property
    def path(self) -> Path:
        return self.__path

    @property  # NOTE no setter for read-only path
    def src(self) -> str:
        return self.__path.resolve().as_posix()

    @property
    def srcname(self) -> str:
        return self.__path.name

    @property
    def season(self) -> hs.Season|None:
        return self.__season

    @season.setter
    def season(self, season: hs.Season|None) -> None:
        self.__season = season

    @property
    def depends(self) -> CoreFile|None:
        return self.__depends

    @depends.setter
    def depends(self, depends: CoreFile|None) -> None:
        self.__depends = depends

    @property
    def logger(self) -> Logger|None:
        return self.__logger

    @logger.setter
    def logger(self, logger: Logger|None) -> None:
        self.__logger = logger

    @property
    def crc32(self) -> str:
        if not self.__crc32: self.__crc32 = getCRC32(self.path, prefix='', pass_not_found=True)
        return self.__crc32

    @property
    def crc(self) -> str:
        return self.crc32

    @property
    def audio_samples(self) -> str:
        if not ENABLE_AUDIO_SAMPLES_IN_VNA: return ''
        if not self.has_audio: return ''
        if not self.__audio_samples: self.__audio_samples = pickAudioSamples(self.path)
        return self.__audio_samples

    #* shotcut access to naming fields ---------------------------------------------------------------------------------

    # naming fields
    @property
    def g(self) -> str:
        if self.depends: return self.depends.g
        if ret := getattr(self, GRPTAG_VAR, ''):
            return ret
        if self.__season:
            return self.__season.g
        return STD_GRPTAG

    @g.setter
    def g(self, v: str) -> None:
        setattr(self, GRPTAG_VAR, v)

    @property
    def t(self) -> str:
        if self.depends: return self.depends.t
        if ret := getattr(self, TITLE_VAR, ''):
            return ret
        if self.__season:
            return self.__season.t
        return FALLBACK_TITLE

    @t.setter
    def t(self, v: str) -> None:
        setattr(self, TITLE_VAR, v)

    @property
    def l(self) -> str:
        if self.depends: return self.depends.l
        return getattr(self, LOCATION_VAR, '')

    @l.setter
    def l(self, v: str) -> None:
        setattr(self, LOCATION_VAR, v)

    @property
    def c(self) -> str:
        if self.depends: return self.depends.c
        return getattr(self, CLASSIFY_VAR, '')

    @c.setter
    def c(self, v: str) -> None:
        if self.depends: self.depends.c = v
        setattr(self, CLASSIFY_VAR, v)

    @property
    def i1(self) -> str:
        if self.depends: return self.depends.i1
        return getattr(self, IDX1_VAR, '')

    @i1.setter
    def i1(self, v: str) -> None:
        setattr(self, IDX1_VAR, v)

    @property
    def i2(self) -> str:
        if self.depends: return self.depends.i2
        return getattr(self, IDX2_VAR, '')

    @i2.setter
    def i2(self, v: str) -> None:
        setattr(self, IDX2_VAR, v)

    @property
    def s(self) -> str:
        if self.depends: return self.depends.s
        return getattr(self, SUPPLEMENT_VAR, '')

    @s.setter
    def s(self, v: str) -> None:
        setattr(self, SUPPLEMENT_VAR, v)

    @property
    def f(self) -> str:
        if self.depends: return self.depends.f
        return getattr(self, FULLDESP_VAR, '')

    @f.setter
    def f(self, v: str) -> None:
        self.t = ''
        self.i1 = ''
        self.i2 = ''
        self.s = ''
        setattr(self, FULLDESP_VAR, v)

    @property
    def x(self) -> str:
        return getattr(self, SUFFIX_VAR, '')

    @x.setter
    def x(self, v: str) -> None:
        setattr(self, SUFFIX_VAR, v)

    @property  # NOTE no setter for read-only extension
    def e(self) -> str:
        return self.ext

    @property
    def dstname(self) -> str:
        grptag = f'[{self.g}]'
        title = self.t
        fullclass = f'[{f}]' if (f := self.f) else ''  #! not every file has this field
        qlabel = f'[{q}]' if (q := self.qlabel) else ''
        tlabel = f'[{t}]' if (t := self.tlabel) else ''
        suffix = (f'.{self.x}' if (self.e in VNx_SUB_EXTS) else f'[{self.x}]') if self.x else ''
        ext = self.e
        return f'{grptag} {title} {fullclass}{qlabel}{tlabel}{suffix}.{ext}'.strip(string.whitespace + '/\\')

    @property
    def dst(self) -> str:
        relative_path = f'{self.l}/{self.dstname}'.strip(string.whitespace + '/\\')
        if self.__season:
            return (Path(self.__season.dst) / relative_path).as_posix()
        else:
            return relative_path

    #* basic file info -------------------------------------------------------------------------------------------------

    @property
    def file_size(self) -> int:
        return int(self.general_tracks[0].file_size)

    @property
    def suffix(self) -> str:
        return self.path.suffix

    @property
    def ext(self) -> str:
        return self.suffix.lower().lstrip('.')

    @property
    def format(self) -> str:
        return ret.lower() if (ret := self.gtr.format) else self.ext

    #* file type -------------------------------------------------------------------------------------------------------

    @property
    def gtr(self) -> Track:
        return self.__mediainfo.general_tracks[0]

    @property
    def is_video(self) -> bool:
        return self.has_video

    @property
    def is_audio(self) -> bool:
        return self.is_audio and not self.is_video

    @property
    def is_image(self) -> bool:
        return (self.ext in VNx_IMG_EXTS) and self.has_image

    @property
    def is_ass(self) -> bool:
        if self.ext not in VNx_SUB_EXTS: return False
        #? this means the encoding of the ass file must be correct - is this intended?
        if not tstAssFile(self.path): return False
        return True

    @property
    def is_archive(self) -> bool:
        if not self.ext in VNx_ARC_EXTS: return False
        if not tstDecompressArchive(self.path): return False
        return True

    @property
    def is_fonts_archive(self) -> bool:
        if not self.is_archive: return False
        filenames = getArchiveFilelist(self.path)
        extensions = set(Path(f).suffix.lower().lstrip('.') for f in filenames)
        if not extensions: return False
        if extensions.difference(COMMON_FONT_EXTS): return False
        return True

    @property
    def is_image_archive(self) -> bool:
        if not self.is_archive: return False
        filenames = getArchiveFilelist(self.path)
        extensions = set(Path(f).suffix.lower().lstrip('.') for f in filenames)
        if not extensions: return False
        if extensions.difference(VNx_IMG_EXTS): return False
        return True

    @property
    def has_video(self) -> bool:
        return bool(self.video_tracks)

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_tracks)

    @property
    def has_menu(self) -> bool:
        return bool(self.menu_tracks)

    @property
    def has_text(self) -> bool:
        #! note this is instable for standalone ass files due to BOM encoding
        return bool(self.text_tracks)

    @property
    def has_image(self) -> bool:
        return bool(self.image_tracks)

    @property
    def has_other(self) -> bool:
        return bool(self.other_tracks)

    @property
    def num_audio(self) -> int:
        return len(self.audio_tracks)

    @property
    def num_menu(self) -> int:
        return len(self.menu_tracks)

    @property
    def num_chap(self) -> int:
        return self.num_menu

    @property
    def menu_timestamps(self) -> list[list[int]]:
        ret = []
        for menu_track in self.menu_tracks:
            menu_dict = menu_track.to_data()
            matches = [re.match(LIBMEDIAINFO_CHAPTER_REGEX, k) for k in menu_dict.keys()]
            matches = [[int(_) for _ in m.groups()] for m in matches if m]
            matches = [(3600000 * m[0] + 60000 * m[1] + m[2]) for m in matches if len(m) == 3]
            ret.append(matches)
        return ret  # the unit is ms

    def countEachTrackType(self) -> dict:
        tracks: dict[str, int] = {}
        for i, t in enumerate(self.tracks[1:], start=1):
            key = (t.format if t.format else t.track_type)
            tracks[key] = tracks.get(key, 0) + 1
        return tracks

    @property
    def has_duration(self) -> bool:
        return not (self.gtr.duration is None)

    @property
    def duration(self) -> int:
        if not self.has_duration: return 0
        return int(float(self.general_tracks[0].duration))  # the unit is ms

    #* to interact with AC ---------------------------------------------------------------------------------------------

    @property
    def qlabel(self) -> str:
        if self.depends: return self.depends.qlabel
        if self.__qlabel is None: self.__qlabel = fmtQualityLabel(self, self.logger)
        return self.__qlabel

    @property
    def tlabel(self) -> str:
        if self.depends: return self.depends.tlabel
        if self.__tlabel is None: self.__tlabel = fmtTrackLabel(self, self.logger)
        return self.__tlabel

    def updateFromNamingDict(self, naming_dict: dict[str, str]) -> None:
        for var in COREFILE_DICT.values():
            if naming := naming_dict.get(var):
                setattr(self, var, naming)

    def copyNaming(self, cf: CF):
        self.l = cf.l
        self.c = cf.c
        self.i1 = cf.i1
        self.i2 = cf.i2
        self.s = cf.s
        self.f = cf.f

    def fmtGeneralDuration(self) -> str:
        t = self.duration
        if t <= 0: return ''
        h, t = divmod(t, 3600000)
        m, t = divmod(t, 60000)
        s, t = divmod(t, 1000)
        return f'{h:02d}:{m:02d}:{s:02d}.{t:03d}'

    def fmtFileSize(self) -> str:
        n = self.file_size
        if n <= 0: return ''
        g, n = divmod(n, 1000**3)
        m, n = divmod(n, 1000**2)
        k, n = divmod(n, 1000**1)
        return ((f'{g:_>2d}g' if g else '___') +
                (f'{m:_>3d}m' if m else '____') +
                (f'{k:_>3d}k' if k else '____') +
                (f'{n:_>3d}' if n else '___'))

    def fmtTrackTypeCounts(self) -> str:
        '''NOTE this function keeps no order of the tracks.'''
        ret = []
        for k, v in self.countEachTrackType().items():
            ret.append(f'{v}x{k}' if v > 1 else f'{k}')
        return '／'.join(ret)

    def fmtTrackTypeCountsWithOrder(self) -> str:
        '''
        NOTE this function keeps the track order when grouping
        HEVC+FLAC+FLAC+AAC+FLAC shows as HEVC／FLAC×2／AAC／FLAC instead of HEVC／FLAC×3／AAC
        '''
        tracks = []
        last = {}
        for i, t in enumerate(self.tracks[1:], start=1):
            key = (t.format if t.format else t.track_type)
            if key in last.keys():
                last[key] += 1
            else:
                if last:
                    last_key = list(last.keys())[0]
                    num = last.pop(last_key)
                    tracks.append(f'{last_key}' + (f'×{num}' if num > 1 else ''))
                last[key] = 1
            if not self.tracks[1:][i:]:  # if no track left
                num = last[key]
                tracks.append(f'{key}' + (f'×{num}' if num > 1 else ''))
        return '／'.join(tracks)

    def digestVideoTracksInfo(self) -> list[str]:
        # hevc|1920×1080|23.98|cfr|10b|main10|yuv420|12345.67s[|Full][|DEFAULT][|Forced][|Delay=?]
        video_infos = []
        for t in self.video_tracks:
            info = []
            # always shown info
            info += [f'{v}'.lower() if (v := t.format) else 'FORMAT?']
            info += [f'{t.width}×{t.height}' + (f'{v}'.upper()[0] if (v := t.scan_type) else '')]  # progressive/interlaced
            info += [f'{t.frame_rate_mode}'.lower()]
            info += [f'{float(v):.2f}'] if (v := t.frame_rate) else ['FPS?']
            info += [f'{v}b'] if (v := t.bit_depth) else ['DEPTH?']
            info += [f'{v}'.split('@')[0].replace(' ', '').replace(':', '').lower()] \
                    if (v := t.format_profile) else ['PROFILE?']
            info += [(f'{v}' if (v := t.color_space) else 'COLOR?') + (f'{v}'.replace(':','') \
                    if (v := t.chroma_subsampling) else '?')]
            info += [f'{float(v)/1000:.2f}s'] if (v := t.duration) else ['TIME?']
            # selective info
            info += [f'{v}'.upper()] if (v := t.language) else ''
            info += ['FULL'] if t.color_range != 'Limited' else ''
            info += ['DEFAULT'] if t.default == 'Yes' else ''
            info += ['FORCED'] if t.forced == 'Yes' else ''
            info += [f'DELAY={v}'] if (v := t.delay) else ''
            video_infos.append('|'.join(info))
        return video_infos

    def digestAudioTracksInfo(self) -> list[str]:
        # flac|6ch[|16b]|48kHz[|750kbps][|DEFAULT][|FORCED][|DELAY=?]
        audio_infos = []
        for t in self.audio_tracks:
            info = []
            # always shown
            info += [f'{info}'.lower()] if (info := t.format) else ['FORMAT?']
            info += [f'{info}ch' if (info := t.channel_s) else 'CHANNEL?']
            info += [f'{info}b'.lower()] if (info := t.bit_depth) else ''  # formats like AAC has no depth info
            info += [f'{info/1000:.0f}kHz'] if (info := t.sampling_rate) else ['KHZ?']
            info += [f'{info/1000:.0f}kbps'] if (info := t.bit_rate) else ''  # formats like AAC have no bit rate mode
            info += [f'{float(info)/1000:.2f}s'] if (info := t.duration) else ['TIME?']
            info += [f'{info}'.lower()] if (info := t.language) else ['LANG?']
            # selective
            info += ['DEFAULT'] if t.default == 'Yes' else ''
            info += ['FORCED'] if t.forced == 'Yes' else ''
            info += [f'DELAY={info}'] if (info := t.delay) else ''
            audio_infos.append('|'.join(info))
        return audio_infos

    def digestTextTracksInfo(self) -> list[str]:
        # PGS|ja[|DEFAULT][|FORCED][×2]
        data = {}
        for t in self.text_tracks:
            info = []
            # always
            info += [f'{info}' if (info := t.format) else 'FORMAT?']
            info += [f'{info}' if (info := t.language) else 'LANG?']
            # selective
            info += ['DEFAULT'] if t.default == 'Yes' else ''
            info += ['FORCED'] if t.forced == 'Yes' else ''
            key = '|'.join(info)
            data[key] = data.get(key, 0) + 1
        return [f'({k})×{v}' for k, v in data.items()]

    def digestMenuTracksInfo(self) -> list[str]:
        # MKV/MKA: ja|7／en|5
        # MP4: 7／5
        menu_infos = []
        for t in self.menu_tracks:
            d = t.to_data()
            keys = [k for k in d.keys() if re.match(LIBMEDIAINFO_CHAPTER_REGEX, k)]
            info = []
            info += [d[keys[0]][:2]] if self.format == 'matroska' else ''
            info += [f'{len(keys)}']
            menu_infos += ['|'.join(info)]
        return menu_infos

    def digestFpsInfo(self) -> list[str]:
        if not self.has_video: return []
        ret = []
        for t in self.video_tracks:
            fps = str(t.frame_rate) if t.frame_rate else 'FPS?'
            st = (f'{v}'.upper()[0] if (v := t.scan_type) else '')
            ret.append(f'{fps}{st}')
        return ret

    def fmtFpsInfo(self) -> str:
        return '／'.join(self.digestFpsInfo())




CF = CoreFile




def toCoreFiles(
    paths: list[str]|list[Path],
    logger: Logger,
    init_crc32: bool = True,
    init_audio_samples: bool = False,
    mp: int = NUM_IO_JOBS
    ) -> list[CF]:

    logger.info(f'Loading files with {mp} workers ...')
    paths = [Path(path) for path in paths]
    if mp > 1:
        with Pool(mp) as pool:
            ret = []
            kwargs = {'init_crc32': init_crc32, 'init_audio_samples': init_audio_samples}
            for path in paths:
                ret.append(pool.apply_async(CoreFile, kwds=kwargs))
            pool.close()
            pool.join()
        cfs = [r.get() for r in ret]
    else:
        cfs = []
        for path in paths:
            cfs.append(CF(path, init_crc32=init_crc32))
    return cfs




def toCoreFilesWithTqdm(
    paths: list[str]|list[Path],
    logger: Logger,
    init_crc32: bool = True,
    init_audio_samples: bool = False,
    mp: int = NUM_IO_JOBS
    ) -> list[CF]:

    logger.info(f'Loading files with {mp} workers ...')
    paths = [Path(path) for path in paths]
    with logging_redirect_tqdm([logger]):
        pbar = tqdm.tqdm(total=len(paths), desc='Loading', unit='file', ascii=True, dynamic_ncols=True)
        if mp > 1:
            with Pool(mp) as pool:
                ret = []
                callback = lambda _: pbar.update(1)
                kwargs = {'path': '', 'init_crc32': init_crc32, 'init_audio_samples': init_audio_samples}
                for path in paths:
                    (kwds := kwargs.copy())['path'] = path
                    ret.append(pool.apply_async(CoreFile, kwds=kwds, callback=callback))
                pool.close()
                pool.join()
            cfs = [r.get() for r in ret]
        else:
            cfs = []
            for path in paths:
                cfs.append(CF(path=path, init_crc32=init_crc32, init_audio_samples=init_audio_samples))
                pbar.update(1)
        pbar.close()
    return cfs
