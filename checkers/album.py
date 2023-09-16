from __future__ import annotations

import time
from logging import Logger
from pathlib import Path

from utils import *
from langs import *
from configs import *
from helpers.album import *
from helpers.summaries import logMusicSummary

from tqdm import tqdm

# class DiscInfo:

#     def __init__(self, path:Path, parent:AlbumInfo) :
#         self.root : Path = path
#         self.parent : AlbumInfo = parent

__all__ = [
    'chkAlbumRoot',
    'chkAlbumDirNaming',
    'chkAlbumFiles',
    'logContentCheck',
    ]




def chkAlbumRoot(root: Path, logger: Logger) -> None:

    if root.name != STD_CDS_DIRNAME:
        logger.error(AR_CAPTITAL_MISTAKE_2.format(STD_CDS_DIRNAME, root.name))

    logger.info(LISTING_FILES_0)
    all_paths = listFile(root)
    cds_paths = listFile(root, ext=ALL_EXTS_IN_CDS)
    for path in set(all_paths).difference(set(cds_paths)):
        logger.error(AR_FOUND_DISALLOWED_FILE_1.format(path))
    for path in listFile(root, ext=ALL_EXTS_IN_CDS, rglob=False):
        logger.error(AR_FOUND_MISPLACED_FILE_2.format(path.name, path.parent))

    logger.info(AR_GATHERING_ALBUM_DIRS_0)
    albums_paths: list[Path] = listAlbumDirs(root, logger=logger)
    if not albums_paths:
        logger.error(AR_GOT_NO_ALBUM_DIR_0)
        return

    logger.info(AR_CHECKING_ALBUM_LAYOUT_0)
    albums_infos: list[AlbumInfo] = []
    for album_path in albums_paths:
        if (album_info := chkAlbumDirNaming(album_path, logger=logger)):
            albums_infos.append(album_info)
    if not albums_infos: logger.error(AR_GOT_NO_VALID_ALBUM_DIR_0)

    logger.info(AR_CHECKING_DIR_CONTENT_0)
    for album_info in albums_infos:
        chkAlbumFiles(album_info, logger=logger)

    logContentCheck(albums_infos, logger=logger)

    if ENABLE_VGMDB:
        logger.info(AR_CHECKING_VGMDB_0)
        for album_info in (pbar := tqdm(albums_infos, ascii=True, dynamic_ncols=True)):
            pbar.set_description(f'VGMDB: {album_info.root.name}')
            lookupVGMDB(album_info, logger=logger)
            time.sleep(1)

    logger.info(AR_GEN_SUMMARY_0)
    logMusicSummary(root, albums_infos, logger=logger)

    credits = [c for c in [ai.credit for ai in albums_infos] if c]
    if credits:
        logger.info('Found the following source credits from txt files:')
        logger.info('\n'.join(credits))




def chkAlbumDirNaming(album_path: Path, logger: Logger) -> AlbumInfo:
    '''
    Check the file layout and names under `album_path`.

    NOTE: this function does NOT check ANY file content.
    It's purely based on filetree and filenames.

    Return: dict
    It returns a processed info dict about the ALBUM, making it easier for later content check.
    If the album folder looks bad, the returned dict will be empty.
    '''

    ok = True
    album_path = Path(album_path)
    dirname = album_path.name

    if DEBUG:
        assert album_path.is_dir()
        assert re.match(ALBUM_DIR_MIN_PATTERN, dirname.lower())

    logger.info(CHECKING_1.format(dirname))

    if not (m := re.match(ALBUM_DIR_FULL_PATTERN, dirname)):
        logger.error(AR_SKIPPED_BY_FAILED_REGEX_1.format(dirname))
        ok = False

        #! do not exit immediately, just mark ok=False and continue
        #! we can still do some layout check until parsed info from dirname is needed

        # TODO: try populating some information from malformed album folder name

        # here summaries the info we need to obtain from album dirname
        ripper, year, month, day = '', 0, 0, 0
        prename, quotation, midname, aftname = '', '', '', ''
        slash, artists, artists_ts = '', '', ''
        edition, edition_name, edition_ts = '', '', ''
        hires, hires_bit, hires_freq, hires_ts = '', 0, 0, ''
        aud_fmts, img_fmts, vid_fmts = '', '', ''

    else:

        (
            ripper,
            year,
            month,
            day,
            prename,
            quotation,
            midname,
            aftname,
            slash,
            artists,
            artists_ts,
            edition,
            edition_name,
            edition_ts,
            hires,
            hires_bit,
            hires_freq,
            hires_ts,
            aud_fmts,
            img_fmts,
            vid_fmts,
            ) = (
                m.group(n) for n in (
                    'eac year month day '
                    'pre quot mid aft '
                    'slash art art_ts '
                    'ed edn ed_ts '
                    'hr bit freq hr_ts '
                    'af if vf'
                    ).split()
                )

        if DEBUG:
            logger.info(
                f'INPUT: {ripper=} {year=} {month=} {day=} '
                f'{prename=} {quotation=} {midname=} {aftname=}'
                f'{slash=} {artists=} {artists_ts=}'
                f'{edition=} {edition_name=} {edition_ts=}'
                f'{hires=} {hires_bit=} {hires_freq=} {hires_ts=}'
                f'{aud_fmts=} {img_fmts=} {vid_fmts=}'
                )

        if ripper:
            logger.error(f'We no longer mark [{ripper}] in album dirname.')

        #* date ******************************************************

        try:
            if day:
                time.strptime(f'{year}{month}{day}', '%y%m%d')
            elif month:
                logger.warning(f'The album date format is not YYMMDD.')
                time.strptime(f'{year}{month}', '%y%m')
            elif year:
                logger.warning(f'The album date format is not YYMMDD.')
                time.strptime(f'{year}', '%Y')
            else:
                logger.warning(f'No album relese date specified.')
        except ValueError:
            logger.error(f'Incorrect album date.')
        year = int(year) if year else 0
        month = int(month) if month else 0
        day = int(day) if day else 0
        if THIS_YEAR < year < 90:
            logger.error(f'Possibly incorrect album year "{year}".')

        #* name ******************************************************

        if not prename:
            logger.warning(f'Missing a proper space after [YYMMDD].')
        elif prename == ' ':
            pass  # this is normal for now
        elif not prename.strip():
            logger.warning(f'Improper spacing after [YYMMDD].')
        elif prename[0] != ' ' or prename[-1] != ' ' or prename[1:-1] != prename.strip():
            logger.warning(f'Improper spacing in "{prename}".')
        prename = prename.strip() if prename else ''
        if '  ' in prename: logger.warning('Double space used in album name.')

        if quotation:
            if not midname or not midname.strip():
                logger.warning(f'The album name between ｢｣ is empty.')
            elif midname.strip() != midname:
                logger.warning(f'Improper spacing around "{midname}".')
                # seems dont need this
                # if  '／' in midname:
                #     logger.info(f'"／" used in album name "{midname}".')
        midname = midname.strip() if midname else ''
        if '  ' in midname: logger.warning('Double space used in album name.')

        match (bool(quotation), bool(slash), bool(aftname.strip()) if aftname else False):
            case (True, _, True):  # 2 cases
                if aftname[1:-1] != aftname.strip():
                    logger.warning(f'Improper spacing around "{aftname}".')
            case (True, True, False):  # 1 case
                if aftname: logger.warning(f'Improper spacing after "｣" and before "／".')
            case (True, False, _):  # 2 cases
                if aftname != ' ': logger.warning(f'Missing a proper space after "｣".')
            case (False, _, _):  # 4 cases
                # NOTE this should be never reached as prename will catch all
                if aftname: logger.warning(f'Improper name part "{aftname}".')
        aftname = aftname.strip() if aftname else ''
        if '  ' in aftname: logger.warning('Double space used in album name.')

        #* artists ***************************************************

        # our full pattern for album dirname will push all irregular '／' to the artists field
        # if running normal, there should be no '／' inside artists
        if slash:  # using slash means there is ARTISTS
            if artists:
                if '／' in artists:
                    logger.error(
                        'Found misused "／" which should be only used inside "｢ALBUM｣" '
                        'or only once for ARTISTS. Other usage is not accepted.'
                        )
                if not artists.strip():
                    logger.error('Found empty ARTISTS.')
                if artists.strip() != artists:
                    logger.error(f'Improper space(s) around "{artists}".')
                if artists_ts != ' ':
                    logger.error('Missing a proper space after "／ARTISTS".')
            artists = artists.strip() if artists else ''
            artists_ts = artists_ts.strip() if artists_ts else ''
            artists = artists + artists_ts  # the regex capture will lack the ending character
        else:
            artists = ''
        if artists and len(artists) > 20:
            logger.warning(f'The artists label "{artists}" is long. Consider removing the artists label.')
        if any(cv in artists.lower() for cv in ('cv', 'c.v')):
            logger.warning('CV labelled in album dirname. Do NOT do that.')
        if any(va in artists.lower() for va in ('va', 'various artists', 'various', 'v.a')):
            logger.error('VA labelled in album dirname. Do NOT do that.')
        if '  ' in artists: logger.warning('Double space used in artists name.')

        #* artists ***************************************************

        if edition:
            logger.info(f'Using irregular edition label "{edition}".')
        edition = edition.strip() if edition else ''
        if edition and not edition_ts:
            logger.error('Missing a proper space after [EDITION].')
        if '  ' in edition: logger.warning('Double space used in edition name.')

        #* hi-res ****************************************************

        if hires:
            if not hires_ts:
                logger.error('Missing a proper space after [HIRES].')
            hires_bit = int(hires_bit)
            hires_freq = int(hires_freq) * 1000
        else:
            hires_bit = 0
            hires_freq = 0

        #* formats ***************************************************

        aud_fmts = aud_fmts.strip().split('+') if aud_fmts else ''
        img_fmts = img_fmts.strip().split('+') if img_fmts else ''
        vid_fmts = vid_fmts.strip().split('+') if vid_fmts else ''

        # TODO rebuild the dirname and compare here

        # if DEBUG:
        #     logger.info(f'PROC: {year=} {month=} {day=} '
        #                 f'{prename=} {midname=} {aftname=}'
        #                 f'{artists=}'
        #                 f'{edition_name=}'
        #                 f'{hires_bit=} {hires_freq=}'
        #                 f'{aud_fmts=} {img_fmts=} {vid_fmts=}')

    # else end
    #***********************************************************************************************
    # now record the information we obtained from album dirname

    ai = AlbumInfo(album_path)
    ai.year, ai.month, ai.day = year, month, day
    ai.prename, ai.midname, ai.aftname = prename, midname, aftname
    ai.artists, ai.edition = artists, edition_name  # TODO if edition, then at most 1 disc
    ai.hr_bit, ai.hr_freq = hires_bit, hires_freq
    ai.has_flac, ai.has_aac, ai.has_mp3 = ('flac' in aud_fmts), ('aac' in aud_fmts), ('mp3' in aud_fmts)
    ai.has_webp, ai.has_jpg, ai.has_vid = ('webp' in img_fmts), ('jpg' in img_fmts), ('mkv' in vid_fmts)

    #***********************************************************************************************

    # txt file can be checked independently
    album_txt_files = listFile(album_path, ext='txt')
    if album_txt_files:
        if len(album_txt_files) > 1:
            logger.error(f'only 1 txt source credit allowed in each album folder (got {len(album_txt_files)}).')
        for txt_file in album_txt_files:
            if txt_file.parent != album_path:
                logger.error(f'The source credit "{txt_file.relative_to(album_path)}" is not located at album root.')
            if txt_file.name != STD_TSDM_CREDIT_TXT_FILENAME:
                logger.info(f'Note a non-TSDM-named source credit "{txt_file.relative_to(album_path)}".')
    ai.txt_files = album_txt_files

    # then determine the usage of each subdirs as below, which results in:
    # `discs_set` may have AUD and MKV and WEBP/JPG
    # `mvs_set` may have MV and WEBP/JPG
    # `bks_set` has WEBP/JPG only

    # conns_set is the parent folder that is used to hold/cluster disc/bk/mv_sets i.e. connecting them
    discs_set: set[Path] = set()
    mvids_set: set[Path] = set()
    scans_set: set[Path] = set()
    miscs_set: set[Path] = set()

    for album_sub_dir in listDir(album_path):

        # empty dir doesn't matter during torrent making, so only give an info notice
        # if not album_sub_dir_files and not album_sub_dir_dirs:
        #     logger.info(f'Empty dir "{album_sub_dir}".')
        #     continue

        # NOTE this log seems unnecessary as non-files folder is legal under CDs
        # if not album_sub_dir_files:
        #     logger.warning(f'Empty dir "{album_sub_dir}". ')
        #     continue

        # if contains any flac/mp3/aac/cue/log -> a 'disc dir'
        if listFile(album_sub_dir, ext=MAIN_EXTS_IN_CDS, rglob=False):
            discs_set.add(album_sub_dir)
            continue

        # then if contains any mkv -> an 'mv dir'
        if listFile(album_sub_dir, ext='mkv', rglob=False):
            mvids_set.add(album_sub_dir)
            logger.info('Found an MV inside the album.')
            continue

        # then if contains any webp/jpg (but cover.jpg) -> 'bk dir'
        if img_files := listFile(album_sub_dir, ext=IMG_EXTS_IN_CDS, rglob=False):
            if len(img_files) == 1 and img_files[0].name.lower() == STD_COVER_FILENAME.lower():
                logger.warning('The Scans dir seemingly contains only a cover.jpg.')
            scans_set.add(album_sub_dir)
            continue

        # if there is still some required files under it, it is a misc dir
        if listFile(album_sub_dir, ext=ALL_EXTS_IN_CDS):
            miscs_set.add(album_sub_dir)
        else:
            logger.warning(
                f'Cannot determine the usage of "{album_sub_dir.relative_to(album_path)}". '
                f'It contains no required file.'
                )

    ai.video_dirs = list(mvids_set)
    ai.scans_dirs = list(scans_set)
    ai.miscs_dirs = list(miscs_set)

    catalog_candidates: list[str] = []

    if not discs_set:
        ok = False

    # if inters := scans_set.intersection(discs_set):
    #     for inter_path in inters:
    #         logger.error(f'CD Scans dir "{inter_path}" should not contain music files.')
    # if inters := scans_set.intersection(mvids_set):
    #     for inter_path in inters:
    #         logger.error(f'CD Scans dir "{inter_path}" should not contain MV files.')

    # the checks later requires album info parsed from dirname
    # if it's already failed, we should stop here

    if not ok:
        return ai

    #* disc checking *******************************************************************************

    hires_discs_set: set[Path] = set()
    split_discs_set: set[Path] = set()
    joint_discs_set: set[Path] = set()
    found_flac, found_mp3, found_aac = False, False, False

    for disc_dir in discs_set:
        logger.info(f'Checking names "{disc_dir.relative_to(album_path)}" (DISC)...')

        # all allowed layout under ALBUM:
        # album_path/* =0
        # album_path/[Editions]/* =1
        # album_path/[MULTIDISC]/* =1
        # album_path/[Editions/MULTIDISC]/* =2
        # going deeper >2 is not allowed

        if len(disc_dir.relative_to(album_path).as_posix().replace('.', '').split('/')) > 2:
            logger.warning(f'The DISC dir "{disc_dir.relative_to(album_path)}" locates too deep inside the album.')

        aud_files = listFile(disc_dir, ext=AUD_EXTS_IN_CDS, rglob=False)
        cue_files = listFile(disc_dir, ext='cue', rglob=False)
        log_files = listFile(disc_dir, ext='log', rglob=False)
        vid_files = listFile(disc_dir, ext='mkv', rglob=False)
        img_files = listFile(disc_dir, ext=IMG_EXTS_IN_CDS, rglob=False)

        # NOTE there is no naming rule for MVs
        if vid_files and len(vid_files) > 1:
            logger.warning(
                'Multiple MV files should better be placed at a dedicated folder, not lying with audio files.'
                )
        for vid_file in vid_files:
            logger.info(f'Note an MV "{vid_file}".')

        # space should not exist in cue/log names
        for file in cue_files + log_files:
            if ' ' in file.stem:
                logger.warning(f'Spacing may be improper in "{file.relative_to(album_path).name}".')

        # start from simpler types
        if ai.is_hires:
            if log_files: logger.error('Hi-Res music should contain no log file.')
            if cue_files: logger.error('Hi-Res music should contain no cue file.')

        disc_aud_exts = set(f.suffix for f in aud_files)
        if DEBUG: assert disc_aud_exts
        if disc_aud_exts:
            if len(disc_aud_exts) != 1:
                logger.error('The disc dir should not contain multiple audio formats (or capitalization mistake).')
            if not all(ext.endswith(('flac', 'mp3', 'm4a')) for ext in disc_aud_exts):
                logger.error(f'The extension capitalization is incorrect under "{disc_dir.relative_to(album_path)}".')
            for disc_aud_ext in disc_aud_exts:
                if disc_aud_ext.lower() == '.flac':
                    found_flac = True
                elif disc_aud_ext.lower() == '.mp3':
                    found_mp3 = True
                elif disc_aud_ext.lower() == '.m4a':
                    found_aac = True
                else:
                    raise ValueError(f'Updated {AUD_EXTS_IN_CDS=}.')
        else:
            raise ValueError()

        # NOTE the user can make arbitrary mistake in album layout
        # to determine if the disc dir is track-split or not, we should only use 'reliable' clues
        # hi-res is always split-track
        if ai.is_hires:
            is_split_track = True
        # if there is a metadata of track position, it's a split-track disc
        elif any(getMediaInfo(f).general_tracks[0].track_name_position for f in aud_files):
            is_split_track = True
        # web source AAC is always split-track
        elif any(f.suffix.lower().endswith('.m4a') for f in aud_files):
            is_split_track = True
        # MP3 is always split tracks in practice. however, this is not 100% reliable, unlike AAC
        elif any(f.suffix.lower().endswith('.mp3') for f in aud_files):
            is_split_track = True
        # if not a hi-res and mp3/aac, then exceeding 80min means track-joint
        elif sum((d if d else 0) for d in [getMediaInfo(f).general_tracks[0].duration for f in aud_files]) \
            > MAX_SINGLE_CD_DURATION_MS:
            is_split_track = False
        # NOTE this is not reliable, if someone forgot to clean "XXXX.utf-8.cue" and "XXXX.cue"
        # elif len(cue_files) >= 2:
        #     is_split_track = False
        # NOTE but log count > 1 is reliable
        elif len(log_files) >= 2:
            is_split_track = False
        # front indexing with a single "01. XXXX.flac" is enough
        elif front_indexed_aud_files := [
            f for f in aud_files if re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower())
            ]:
            is_split_track = True
            if front_indexed_aud_files and (len(front_indexed_aud_files) != len(aud_files)):
                logger.error(
                    'The disc dir seems to contain both split/joint-track audio. '
                    'It will be treated as track-split disc.'
                    )
        # if we find a cue named with the same as another audio file, it's a track-joint disc
        elif set(cue_file.name for cue_file in cue_files).intersection(set(aud_file.name for aud_file in aud_files)):
            is_split_track = False
        # if we find a log named with the same as another audio file, it's a track-joint disc
        elif set(log_file.name for log_file in log_files).intersection(set(aud_file.name for aud_file in aud_files)):
            is_split_track = False
        # check `configs` for the explanation
        elif len(aud_files) >= MIN_NUM_AUDIO_TO_SEEN_AS_SPLIT_TRACK_DISC:
            is_split_track = True
        # NOTE if all above criteria failed, we cant image what the user is doing with the ALBUM
        else:  # now we try some unreliable clues
            # if num_aud == num_cue, hopefully it's joint
            if len(aud_files) == len(cue_files):
                is_split_track = False
            # 1 single flac, 0 or 1 log, no track idx of any kind, hopefully it's joint
            elif len(aud_files) == 1:
                is_split_track = False
            else:
                # many flac, no enough cue, no log, no idx info of any kind, 80min below, what should we do?
                logger.warning(
                    f'The audios under "{disc_dir.relative_to(album_path)}" is too strange. '
                    'It will be treated as track-split disc.'
                    )
                is_split_track = False

        if is_split_track:  # for track-split disc

            if ai.is_hires:  # hi-res
                hires_discs_set.add(disc_dir)
            else:
                split_discs_set.add(disc_dir)

            indexed_files: list[Path] = [
                f for f in aud_files if re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower())
                ]
            for non_idxed_file in (set(aud_files) - set(indexed_files)):
                logger.warning(f'Not properly index-named audio file "{non_idxed_file.relative_to(album_path)}".')

            indices: list[str] = [
                re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower()).group('idx') for f in indexed_files
                ]
            trnames: list[str] = [
                re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower()).group('trname') for f in indexed_files
                ]
            spaces: list[str] = [
                re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower()).group('space') for f in indexed_files
                ]
            dots: list[str] = [
                re.match(FRONT_INDEXED_TRACKNAME_PATTERN, f.name.lower()).group('dot') for f in indexed_files
                ]

            if DEBUG: assert all(idx.isdigit() for idx in indices)
            indices_int_set = set(int(idx) for idx in indices)  # use set to deduplicate
            if indices_int_set and ((len(indices_int_set) != len(indices)) \
            or min(indices_int_set) != 1 \
            or sorted(indices_int_set) != list(range(1, max(indices_int_set)+1))):
                logger.error(f'The split tracks are not properly indexed.')
            if not all(trname.strip() for trname in trnames):
                logger.warning(f'Some track name is empty under "{disc_dir.relative_to(album_path)}".')
            if (not all(dots)) or (not all(spaces)):
                logger.warning(
                    f'Some track name is missing the required ". " between index and trackname. "{disc_dir.relative_to(album_path)}".'
                    )

            # NOTE we cannot check the split tracks filename is correct or not for now, which is done at later metadata lookup stage
            if cue_files: logger.error(f'Track-split disc dir should contain no CUE file (got {len(cue_files)}).')
            if len(log_files) > 1:
                logger.error(f'At most 1 EAC LOG can be placed for track-split disc (got {len(log_files)}).')
            # NOTE we cannot check the log's filename for now, which is done at later metadata lookup stage
            if img_files: logger.error(f'Track-split disc dir should contain no COVER file (got {len(img_files)}).')

        else:  # for track-joint disc
            joint_discs_set.add(disc_dir)

            # NOTE we cannot check the audio/cue/log's filename for now, which is done at later metadata lookup stage
            if len(cue_files) != len(aud_files):
                logger.error(
                    f'Track-joint disc dir must contain the same amount of CUE files and AUDIO files '
                    f'(got {len(cue_files)} expect {len(aud_files)}).'
                    )
            for cue_file in cue_files:
                if not any(cue_file.with_suffix(ext).is_file() for ext in (f'.{e}' for e in AUD_EXTS_IN_CDS)):
                    logger.error(
                        f'Cannot find the counterpart track-joint audio with the same name of "{cue_file.relative_to(album_path)}".'
                        )
            if log_files:  # however, no log file is OK and common
                if len(log_files) > len(aud_files):
                    logger.error(
                        f'The amount of EAC/XLD log files exceeds the number of audio files '
                        f'(got {len(log_files)} expect {len(aud_files)}).'
                        )
                if len(log_files) < len(aud_files):
                    logger.warning(
                        f'Not all joint-track disc got a LOG file '
                        f'(got {len(log_files)} expect {len(aud_files)}).'
                        )
            for log_file in log_files:
                if not any(log_file.with_suffix(ext).is_file() for ext in (f'.{e}' for e in AUD_EXTS_IN_CDS)):
                    logger.error(
                        f'Cannot find the counterpart track-joint audio with the same name of "{log_file.relative_to(album_path)}".'
                        )
            if len(img_files) > 1:
                logger.error(f'At most 1 COVER can be placed for track-joint disc (got {len(img_files)}).')
            if img_files and img_files[0].name != STD_COVER_FILENAME:
                logger.warning(
                    f'The cover filename is incorrect '
                    f'(expect "{STD_COVER_FILENAME}" got "{img_files[0].name}")'
                    )

        if disc_dir != album_path and re.match(POSSIBLE_CATALOG_REGEX, disc_dir.name):
            catalog_candidates.append(disc_dir.name.lower())
        for file in (log_files + cue_files + aud_files):
            if re.match(POSSIBLE_CATALOG_REGEX, file.stem):
                catalog_candidates.append(file.stem.lower())

    ai.hires_discs = list(hires_discs_set)
    ai.split_discs = list(split_discs_set)
    ai.joint_discs = list(joint_discs_set)

    #* mv checking *********************************************************************************

    found_vid = False
    distances_to_album_root = []
    for mv_dir in mvids_set:
        logger.info(f'Checking names "{mv_dir.relative_to(album_path)}" (MV)...')

        # album_path/* =0
        # album_path/[Any]/* =1
        # album_path/[Edition/SPs]/* =2
        # going deeper >2 is not allowed

        distance_to_album_root = len(mv_dir.relative_to(album_path).as_posix().replace('.', '').split('/'))
        if distance_to_album_root > 2:
            logger.warning(f'The MV dir "{mv_dir.relative_to(album_path)}" is misplaced.')
        distances_to_album_root.append(distance_to_album_root)

        mv_files = listFile(mv_dir, ext='mkv', rglob=False)
        if DEBUG: assert mv_files
        found_vid = True if mv_files else found_vid

        img_files = listFile(mv_dir, ext=IMG_EXTS_IN_CDS, rglob=False)
        if img_files:
            logger.error(f'The MV dir "{mv_dir.relative_to(album_path)}" should not contain any image.')

        if len(mv_files) == 1 and re.match(POSSIBLE_CATALOG_REGEX, mv_files[0].stem):
            catalog_candidates.append(mv_files[0].stem.lower())
        if mv_dir.name.lower() not in 'sps' and re.match(POSSIBLE_CATALOG_REGEX, mv_dir.name):
            catalog_candidates.append(mv_dir.name.lower())

    if len(set(distances_to_album_root)) > 1:
        logger.warning(f'Found different MV placement styles for "{STD_BKS_DIRNAME}" to "{album_path}".')

    #* bk checking *********************************************************************************

    found_webp, found_jpg = False, False
    distances_to_album_root = []
    for scan_dir in scans_set:
        logger.info(f'Checking names "{scan_dir.relative_to(album_path)}" (BK)...')

        # placing at root =0 is not allowed
        # album_path/[Scans]/* =1
        # album_path/[Scans/Editions]/* =2
        # album_path/[Scans/Editions/Any]/* =3
        # going deeper >3 is not allowed

        distance_to_album_root = len(scan_dir.relative_to(album_path).as_posix().replace('.', '').split('/'))
        if not (1 <= distance_to_album_root <= 3):
            logger.warning(f'The SCANS dir "{scan_dir.relative_to(album_path)}" is misplaced.')
        if (distance_to_album_root == 1) or (scan_dir.parent in discs_set):
            if scan_dir.name != STD_BKS_DIRNAME:
                logger.error(
                    f'The SCANS dir "{scan_dir.relative_to(album_path)}" should be named as "{STD_BKS_DIRNAME}".'
                    )
        distances_to_album_root.append(distance_to_album_root)

        if STD_BKS_DIRNAME not in scan_dir.relative_to(album_path).as_posix():
            logger.error(f'Cannot find a parent "{STD_BKS_DIRNAME}" dir for "{scan_dir}".')

        webp_files = listFile(scan_dir, ext='webp', rglob=False)
        jpeg_files = listFile(scan_dir, ext='jpg jpeg'.split(), rglob=False)
        if DEBUG: assert webp_files or jpeg_files
        found_webp = True if webp_files else found_webp
        found_jpg = True if jpeg_files else found_jpg

        if scan_dir.name.lower() != 'scans' and re.match(POSSIBLE_CATALOG_REGEX, scan_dir.name):
            catalog_candidates.append(scan_dir.name.lower())

    if len(set(distances_to_album_root)) > 1:
        logger.warning(f'Found different SCANS placement styles for "{STD_BKS_DIRNAME}" to "{album_path}".')

    founds = [found_flac, found_mp3, found_aac, found_vid, found_webp, found_jpg]
    labels = ['has_flac', 'has_mp3', 'has_aac', 'has_vid', 'has_webp', 'has_jpg']
    for found, label in zip(founds, labels):
        if found and not getattr(ai, label):
            logger.error(f'The album contains {label.upper()} but is not labelled with "{label}".')
        if not found and getattr(ai, label):
            logger.error(f'The album is labelled with "{label}" but contains no {label.upper()}.')

    ai.catalogs = list(set(catalog_candidates))

    if DEBUG:
        logger.info('CATALOG: ' + '|'.join(ai.catalogs))

    return ai




def chkAlbumFiles(album: AlbumInfo, logger: Logger):

    if not album: return album
    logger.info(f'Checking files in "{album.root.name}"...')

    chkSplitDiscs(album, logger)
    chkJointDiscs(album, logger)
    chkHiResDiscs(album, logger)
    chkScanDirs(album, logger)
    chkMvDirs(album, logger)
    chkCreditFiles(album, logger)

    # for i, msg in album.logs:
    #         match i:
    #             case 0: # info
    #                 logger.info(msg)
    #             case 1: # warning
    #                 logger.warning(msg)
    #             case 2: # error
    #                 logger.error(msg)
    #             case _:
    #                 raise ValueError

    # NOTE: we didn't see multiprocessing is noticeably faster
    # mp overhead in creating/destroying process is very expensive

    # pbar = tqdm.tqdm(total=album_info.total_items, desc='Checked', unit='', unit_scale=False, ascii=True, dynamic_ncols=True)

    # pool = Pool()
    # for sa_dir in album_info.split_discs:
    #     a_infos.append(pool.apply_async(chkSplitAudioDir, args=(sa_dir, album_info)))
    # for ja_dir in album_info.joint_discs:
    #     a_infos.append(pool.apply_async(chkJointAudioDir, args=(ja_dir, album_info)))
    # for bk_dir in album_info['d_bk']:
    #     b_infos.append(pool.apply_async(chkScansDir, args=(bk_dir, album_info)))
    # for mv_dir in album_info['d_mv']:
    #     m_infos.append(pool.apply_async(chkMvDir, args=(mv_dir, album_info)))
    # for txt_file in album_info['f_txt']:
    #     t_infos.append(pool.apply_async(chkTxtFile, args=(txt_file, album_info)))

    # n_completed = 0
    # while n_completed < n_total:
    #     n_ready = sum(r.ready() for r in results)
    #     if n_new := (n_ready - n_completed):
    #         pbar.update(n_new)
    #     n_completed = n_ready
    #     time.sleep(0.5)

    # pool.close()
    # pool.join()
    # a_infos = [r.get() for r in a_infos]
    # b_infos = [r.get() for r in b_infos]
    # m_infos = [r.get() for r in m_infos]
    # t_infos = [r.get() for r in t_infos]
    # pbar.close()




def logContentCheck(albums: list[AlbumInfo], logger: Logger):

    for album in albums:
        logger.info(f'Reporting for "{album.root.name}"...')
        for i, msg in album.logs:
            match i:
                case 0:  # info
                    logger.info(msg)
                case 1:  # warning
                    logger.warning(msg)
                case 2:  # error
                    logger.error(msg)
                case _:
                    raise ValueError




def _chkSplitDiscImpl(self, disc_dir: Path):

    aroot = self.root

    #* audio check ***************************************************

    aud_files = listFile(disc_dir, ext=AUD_EXTS_IN_CDS, rglob=False)
    aud_minfos = [getMediaInfo(f) for f in aud_files]

    valid_aud_files = []
    valid_aud_minfos = []
    for f, m in zip(aud_files, aud_minfos):
        if m.audio_tracks:
            valid_aud_files.append(f)
            valid_aud_minfos.append(m)
        else:
            self.logs.append((2, f'Not an audio file "{f.relative_to(aroot)}".'))

    aud_gtrs = [m.general_tracks[0] for m in valid_aud_minfos]
    aud_atrs = [m.audio_tracks[0] for m in valid_aud_minfos]

    seen_album_names = []
    seen_artists = []

    for aud_file, gtr, atr in zip(valid_aud_files, aud_gtrs, aud_atrs):
        rel_path = aud_file.relative_to(aroot)
        match gtr.format:
            case 'FLAC':
                expected_ext = '.flac'
            case 'MPEG Audio':
                expected_ext = '.mp3'
            case 'AAC LC':
                expected_ext = '.m4a'
            case _:
                raise ValueError(f'Updated {AUD_EXTS_IN_CDS=}.')
        if aud_file.suffix.lower() != expected_ext:
            self.logs.append((2, f'File extension mismatches actual file content "{rel_path}".'))

        if self.hr_bit and self.hr_bit != atr.bit_depth:
            self.logs.append((2, f'Hi-Res bit depth label is incorrect for "{rel_path}".'))
        if self.hr_freq and self.hr_freq != atr.sampling_rate:
            self.logs.append((2, f'Hi-Res sampling rate label is incorrect for "{rel_path}".'))

        if gtr.format == 'FLAC':
            wav_filesize = atr.bit_depth * atr.sampling_rate * atr.channel_s * atr.duration / 8 / 1000
            if atr.stream_size > wav_filesize * 0.9:
                self.logs.append((1, f'FLAC compression ratio is too low for "{rel_path}".'))
        if atr.channel_s != 2:
            self.logs.append((2, f'Channel count is not 2 for "{rel_path}".'))
        if atr.stream_size / gtr.file_size < 0.9:
            self.logs.append((1, f'Embedded cover art may be too large for "{rel_path}".'))

        if m := re.match(FRONT_INDEXED_TRACKNAME_PATTERN, aud_file.name):
            idx, trname = m.group('idx'), m.group('trname')
            if gtr.track_name and trname and not matchTrackName(trname, gtr.track_name):
                self.logs.append((2, f'Track name mismatches "{rel_path}".'))
            if gtr.track_name_position and not matchIndex(idx, gtr.track_name_position):
                self.logs.append((2, f'Track index mismatches "{rel_path}".'))
            if gtr.track_name_total and not matchIndex(len(aud_files), gtr.track_name_total):
                self.logs.append((2, f'Total track count mismatches "{rel_path}".'))

        if gtr.album: seen_album_names.append(gtr.album)
        if gtr.performer: seen_artists.append(gtr.performer)
        if gtr.album_performer: seen_artists.append(gtr.album_performer)
        if gtr.composer: seen_artists.append(gtr.composer)
        if gtr.album_composer: seen_artists.append(gtr.album_composer)

        if not tstFFmpegDecode(aud_file):
            self.logs.append((2, f'Decoding "{rel_path}" failed.'))

    seen_artists = list(set(seen_artists))
    if seen_artists and self.artists and not matchArtistsName(self.artists, seen_artists):
        self.logs.append((1, f'The ARTIST label in dirname is not seen in audio metadata.'))

    seen_album_names = list(set(seen_album_names))
    if len(seen_album_names) > 1:
        self.logs.append((1, f'Audio metadata contains different album names under "{disc_dir.relative_to(aroot)}".'))
    album_name_matched = matchAlbumName(self.prename, self.midname, seen_album_names)
    if not album_name_matched:
        self.logs.append((1, f'The album name in dirname is not seen in audio metadata data.'))

    #* log check *****************************************************

    # TODO add more LOG check
    log_files = listFile(disc_dir, ext='log', rglob=False)
    for log_file in log_files:
        if tstFileEncoding(log_file, 'utf-16-le'):
            pass
        elif tstFileEncoding(log_file, 'utf-8-sig'):
            self.logs.append((
                0,
                f'EAC LOG "{log_file.relative_to(disc_dir)}" '
                'should be better preserved as UTF-16-LE instead of UTF-8-BOM.'
                ))
        else:
            self.logs.append((2, f'EAC LOG "{log_file.relative_to(disc_dir)}" decoding failed.'))

    #* img check *****************************************************

    img_files = listFile(disc_dir, ext=IMG_EXTS_IN_CDS, rglob=False)
    for img_file in img_files:
        if not tstFFmpegDecode(img_file):
            self.logs.append((2, f'Decoding "{img_file.relative_to(aroot)}" failed.'))
        if img_file.name == 'Cover.jpg':
            iinfo = getMediaInfo(img_file).image_tracks[0]
            if (iinfo.width and iinfo.width > NORMAL_COVER_ART_LENGTH) \
            or (iinfo.height and iinfo.height > NORMAL_COVER_ART_LENGTH) \
            or (iinfo.stream_size and iinfo.stream_size > NORMAL_COVER_ART_FILESIZE):
                self.logs.append((1, f'The cover art "{img_file.relative_to(aroot)}" is too large.'))
            if not tstFFmpegDecode(img_file):
                self.logs.append((2, f'Decoding "{img_file.relative_to(aroot)}" failed.'))




def chkHiResDiscs(album: AlbumInfo):

    for disc_dir in album.hires_discs:
        _chkSplitDiscImpl(disc_dir)




def chkSplitDiscs(self):

    for disc_dir in self.split_discs:
        self._chkSplitDiscImpl(disc_dir)




def chkJointDiscs(self):

    aroot: Path = self.root
    logs: list[tuple[int, str]] = []

    for disc_dir in self.joint_discs:

        #* audio check ***************************************************

        aud_files = listFile(disc_dir, ext=AUD_EXTS_IN_CDS, rglob=False)
        aud_minfos = [getMediaInfo(f) for f in aud_files]

        valid_aud_files = []
        valid_aud_minfos = []
        for f, m in zip(aud_files, aud_minfos):
            if m.audio_tracks:
                valid_aud_files.append(f)
                valid_aud_minfos.append(m)
            else:
                logs.append((2, f'Not an audio file "{f.relative_to(aroot)}".'))

        aud_gtrs = [m.general_tracks[0] for m in valid_aud_minfos]
        aud_atrs = [m.audio_tracks[0] for m in valid_aud_minfos]

        for aud_file, gtr, atr in zip(valid_aud_files, aud_gtrs, aud_atrs):
            rel_path = aud_file.relative_to(aroot)
            match gtr.format:
                case 'FLAC':
                    expected_ext = '.flac'
                case 'MPEG Audio':
                    expected_ext = '.mp3'
                case 'AAC LC':
                    expected_ext = '.m4a'
                case _:
                    raise ValueError(f'Updated {AUD_EXTS_IN_CDS=}.')
            if aud_file.suffix.lower() != expected_ext:
                logs.append((2, f'File extension mismatches actual file content "{rel_path}".'))

            if gtr.format == 'FLAC':
                wav_filesize = atr.bit_depth * atr.sampling_rate * atr.channel_s * atr.duration / 8 / 1000
                if atr.stream_size > wav_filesize * 0.9:
                    logs.append((1, f'FLAC compression ratio is too low for "{rel_path}".'))
            if atr.channel_s != 2:
                logs.append((2, f'Channel count is not 2 for "{rel_path}".'))
            if atr.stream_size / gtr.file_size < 0.9:
                logs.append((1, f'Embedded cover art may be too large for "{rel_path}".'))

            seen_artists = []
            if gtr.performer: seen_artists.append(gtr.performer)
            if gtr.album_performer: seen_artists.append(gtr.album_performer)
            if gtr.composer: seen_artists.append(gtr.composer)
            if gtr.album_composer: seen_artists.append(gtr.album_composer)
            if seen_artists and self.artists and not matchArtistsName(self.artists, seen_artists):
                logs.append((
                    1,
                    f'The ARTIST label in dirname is not seen in audio metadata under "{disc_dir.relative_to(aroot)}".'
                    ))

            if gtr.album and not matchAlbumName(self.prename, self.midname, gtr.album):
                logs.append((
                    1,
                    f'The album name in dirname is not seen in audio metadata data under "{disc_dir.relative_to(aroot)}".'
                    ))

            if not tstFFmpegDecode(aud_file):
                logs.append((2, f'Decoding "{aud_file.relative_to(aroot)}" failed.'))

        #* cue check *****************************************************

        # TODO use utils.cuesheet to better check the files
        cue_files = listFile(disc_dir, ext='cue', rglob=False)
        for cue_file in cue_files:
            if tstFileEncoding(cue_file, 'utf-8-sig'):
                content = cue_file.read_text(encoding='utf-8-sig')
                if m := re.search(CUE_FILENAME_LINE_REGEX, content):
                    filename = m.group('filename')
                    if cue_file.with_name(filename) not in aud_files:
                        logs.append(
                            (2, f'Cannot find "{filename}" specified in CUESHEET "{cue_file.relative_to(aroot)}".')
                            )
            else:
                logs.append((2, f'Failed to parse "{cue_file.relative_to(aroot)}".'))

        #* log check *****************************************************

        log_files = listFile(disc_dir, ext='log', rglob=False)
        for log_file in log_files:
            if tstFileEncoding(log_file, 'utf-16-le'):
                pass
            elif tstFileEncoding(log_file, 'utf-8-sig'):
                logs.append((
                    1,
                    f'EAC LOG "{log_file.relative_to(aroot)}" '
                    'should be better preserved as UTF-16-LE instead of UTF-8-BOM.'
                    ))
            else:
                logs.append((2, f'EAC LOG "{log_file.relative_to(aroot)}" decoding failed.'))

        #* img check *****************************************************

        img_files = listFile(disc_dir, ext=IMG_EXTS_IN_CDS, rglob=False)
        for img_file in img_files:
            if not tstFFmpegDecode(img_file):
                logs.append((2, f'Decoding "{img_file.relative_to(aroot)}" failed.'))
            if img_file.name == 'Cover.jpg':
                iinfo = getMediaInfo(img_file).image_tracks[0]
                if (iinfo.width and iinfo.width > NORMAL_COVER_ART_LENGTH) \
                or (iinfo.height and iinfo.height > NORMAL_COVER_ART_LENGTH) \
                or (iinfo.stream_size and iinfo.stream_size > NORMAL_COVER_ART_FILESIZE):
                    logs.append((1, f'The cover art "{img_file.relative_to(aroot)}" is too large.'))
                if not tstFFmpegDecode(img_file):
                    logs.append((2, f'Decoding "{img_file.relative_to(aroot)}" failed.'))

    self.logs += logs




def chkScansDirs(self):

    logs: list[tuple[int, str]] = []

    for scans_dir in self.scans_dirs:
        # NOTE Scans checking is now done in ScansRechecker.py for now
        pass

    self.logs += logs




def chkMvDir(self):
    logs: list[tuple[int, str]] = []
    # TODO what we can check for MV?
    self.logs += logs




def chkCreditFiles(self):

    logs: list[tuple[int, str]] = []
    credit_msgs = list()

    for path in self.txt_files:
        if tstFileEncoding(path, 'utf-8-sig'):
            content = path.read_text('utf-8-sig')
            if not content.startswith(STD_TSDM_CREDIT_TEXT):
                if path.name == STD_TSDM_CREDIT_TEXT:
                    logs.append((2, 'Not using TSDM credit text.'))
                    credit_msgs.append(content.strip().replace('\n', ' '))
                else:
                    logs.append((0, 'Not using TSDM credit text.'))
                    credit_msgs.append(content.strip().replace('\n', ' '))
            else:
                credit_msgs.append(DEFAULT_TSDM_CREDIT)
                credit_msg = content.replace(STD_TSDM_CREDIT_TEXT, '').strip().replace('\n', ' ')
                if credit_msg:
                    logs.append((0, f'Found custom lines in TSDM credit text: "{credit_msg}".'))
                    credit_msgs.append(credit_msg)
        else:
            logs.append((2, 'File encoding error (not utf-8-bom).'))

    credit_msgs = list(credit_msgs)
    if DEBUG: logs.append((0, 'credits: ' + ('|'.join(credit_msgs))))
    self.credits = list(set(credit_msgs))

    self.logs = logs
    return self
