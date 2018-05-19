import ffprobe
import dateparser
import datetime
from dateutil.relativedelta import relativedelta as rd
import io
import json
import os
import shutil
import itertools
from tzlocal import get_localzone

class Video:
    def __init__(self, key, title, creator, year, description, filename):
        self._duration = None

        self.key = key
        self.title = title
        self.creator = creator
        self.year = year
        self.description = description
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Couldn't find video file '{filename}'")
        self.filename = filename


    @property
    def duration(self):
        if self._duration is None:
            self._duration = ffprobe.duration(self.filename)
        return self._duration

class Schedule:
    def __init__(self, start_datetime, days):
        self.start_datetime = start_datetime
        self.days = days
        self.videos = []

    def append(self, video):
        self.videos.append(video)

    def unlooped_programming_duration(self):
        return sum(v.duration for v in self.videos)

    def looped_programming(self):
        t = self.start_datetime
        end_t = t + datetime.timedelta(days=self.days)
        for video in itertools.cycle(self.videos):
            yield t, video
            t += datetime.timedelta(seconds = video.duration)
            if t > end_t:
                break

    def readable(self, tz=None):
        if tz is None:
            tz = get_localzone()
        out = io.StringIO()
        fmt = 'Total schedule programming: {0.days} days {0.hours} hours {0.minutes} minutes {0.seconds} seconds\n'
        out.write(fmt.format(rd(seconds=self.unlooped_programming_duration())))
        out.write(f"(Will loop if necessary to hit {self.days} days of programming)\n")
        last_day = None
        for t, video in self.looped_programming():
            t_in_tz = t.astimezone(tz)
            #print(t_in_tz)
            if last_day != t_in_tz.date():
                last_day = t_in_tz.date()
                out.write(f"{t_in_tz.strftime('%A %B %d')}\n")

            t_string = t_in_tz.strftime("%H:%M:%S")
            out.write(f"""
    {t_string}
        {video.title} — {video.year}
        {video.creator}

        {video.description}
""")
                
        return out.getvalue()

    def write_human_html(self, tz=None):
        pass

    def write_schedule_json(self, output_file):
        result = []
        for t, video in self.looped_programming():
            # We'll write everything as UTC timestamps
            timestamp = t.timestamp()
            result.append((timestamp, video.key))
        json.dump(result, output_file)


def load_videos(metadata_file, directory='videos'):
    videos = {}
    for key, val in json.load(open(metadata_file)).items():
        val['filename'] = os.path.join(directory, val['filename'])
        val['key'] = key
        videos[key] = Video(**val)

    return videos


def load_schedule(schedule_file, videos, start_date, days):
    sched_keys = json.load(open(schedule_file))

    sched = Schedule(start_date, days)
    
    for key in sched_keys:
        if key not in videos:
            raise ValueError(f"Video with key \"{key}\" in schedule not found in metadata")
        sched.append(videos[key])
    return sched

def copy_static_files(static_dir, build_dir):
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    shutil.copytree(static_dir, build_dir)


def main(schedule_file, metadata_file, start_date, days):
    start_date = parse_date(start_date)
    videos = load_videos(metadata_file)
    sched = load_schedule(schedule_file, videos, start_date, days)
    print(sched.readable())

    copy_static_files("static", "build")

    shutil.copy2(metadata_file, "build/metadata.json")

    with open("build/schedule.json", "w") as out_file:
        sched.write_schedule_json(out_file)



def parse_date(date_string):
    d = dateparser.parse(date_string,
            settings = {'RETURN_AS_TIMEZONE_AWARE': True, 'TO_TIMEZONE': 'UTC'})
    return d

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description = "Generate a BUMP TV schedule")
    parser.add_argument("--schedule-file", "-s", default="sample_schedule.json")
    parser.add_argument("--metadata-file", "-m", default="sample_metadata.json")
    parser.add_argument("--start-date", "-d",
            default='midnight',
            help="The start date. Could be 'YYYY-MM-DD', or 'tomorrow' or 'in 3 days'. The default is 'midnight'")
    parser.add_argument("--days", "-l", type=int,
            default = 7,
            help="How may days of programming to generate? Will loop the schedule if insufficiently long")
            
    args = parser.parse_args()
    main(**vars(args))

