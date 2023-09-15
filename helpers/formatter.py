from __future__ import annotations

from pathlib import Path
from logging import Logger

from configs import *
from utils import *
from langs import *
from .misc import *
import helpers.corefile as hcf


__all__ = ['fmtQualityLabel', 'fmtTrackLabel']




def fmtSeriesRootName(grp='', title='', suffix='') -> str:
    return SERIES_DIR_FMT.format(grp=grp, title=title, suffix=suffix).strip()




def fmtSeasonRootName(grp='', title='', quality='', suffix='') -> str:
    return SEASON_DIR_FMT.format(grp=grp, title=title, quality=quality, suffix=suffix).strip()




def fmtQualityLabel(cf: hcf.CF, logger: Logger|None = None) -> str:

    # files without video track have no quality label
    if not cf.video_tracks: return ''

    vtr = cf.video_tracks[0]

    h = int(vtr.height) if vtr.height else 0
    h = 1080 if (MIN_VID_HEIGHT_TO_STILL_LABEL_AS_1080 <= h <= 1080) else h

    format = (vtr.format if vtr.format else '').lower()
    profile = (vtr.format_profile if vtr.format_profile else '').split('@')[0].replace(' ', '')

    p = ''
    if format == 'hevc':
        if profile == 'Main10':
            p = 'Ma10p'
        elif profile == 'Main':
            p = ''
        elif profile == 'FormatRange' and vtr.bit_depth == 10 and vtr.chroma_subsampling == '4:4:4':
            p = 'Ma444-10p'
        else:
            if logger: logger.warning(UNHANDLED_HEVC_PROFILE_1.format(profile))
    elif format == 'avc':
        if profile == 'High10':
            p = 'Hi10p'
        elif profile == 'High':
            p = ''
        elif profile == 'High4:4:4Predictive':
            p = 'Hi444pp'  #
        else:
            if logger: logger.warning(UNHANDLED_AVC_PROFILE_1.format(profile))
    else:
        if logger: logger.warning(UNHANDLED_VID_FMT_1.format(format))

    st = 'i' if vtr.scan_type == 'Interlaced' else 'p'  # actually we don't have any interlaced video
    return f'{p}_{h}{st}' if p else f'{h}{st}'




def fmtTrackLabel(cf: hcf.CF|MI, logger: Logger|None = None) -> str:

    if not cf.video_tracks: return ''

    tracks = {}
    for t in (cf.video_tracks + cf.audio_tracks):
        if t.format:
            format = t.format.lower()
            tracks[format] = tracks.get(format, 0) + 1

    tlabel = ''

    if n := tracks.pop('hevc', 0):
        tlabel += (f'{n}x265' if n > 1 else f'x265')
    elif n := tracks.pop('avc', 0):
        tlabel += (f'{n}x264' if n > 1 else f'x264')
    else:
        raise ValueError  # it should be impossible to reach here if return if not minfo.video_tracks

    if n := tracks.pop('flac', 0):
        tlabel += (f'_{n}flac' if n > 1 else f'_flac')

    # TODO: do we need to care about the order of the following?

    if n := tracks.pop('aac', 0):
        tlabel += (f'_{n}aac' if n > 1 else f'_aac')

    if n := tracks.pop('ac3', 0):
        tlabel += (f'_{n}ac3' if n > 1 else f'_ac3')

    if n := tracks.pop('dts', 0):
        tlabel += (f'_{n}dts' if n > 1 else f'_dts')

    for k in tracks.keys():
        if logger: logger.warning(UNHANDLED_FMT_1.format(k))

    return tlabel
