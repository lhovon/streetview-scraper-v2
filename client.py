import os
import math
import json
import time
import argparse
import traceback

from pathlib import Path
from random import randrange
from dotenv import dotenv_values

from multiprocessing import Pool
from selenium.webdriver import chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException, JavascriptException, WebDriverException
from example_cases import EXAMPLE_CASES

# Read in the database configuration from a .env file
ENV = dotenv_values(".env")

JS_MOVE_RIGHT = "moveRight();"
JS_MOVE_LEFT = "moveLeft();"
JS_ADJUST_HEADING = "adjustHeading(%(deg)s, %(pitch)s);"
JS_RESET_CAMERA = "resetCamera(%(pitch)s);"
JS_CHANGE_ZOOM = "window.sv.setZoom(%(zoom)s);"
JS_RESET_INITIAL_POSITION = "window.sv.setPano(document.getElementById('initial-pano').innerText);"
# Change the date of streetview panos
JS_CHANGE_DATE = """
    window.sv.setPano('%(pano)s');
    document.getElementById('initial-pano').innerText = '%(pano)s';
    document.getElementById('current-date').innerText = '%(date)s';
"""
# Fetch the initial panorama for a new location and update the street view
JS_CHANGE_LOCATION = """
    changeMapPosition(%(lat)s, %(lng)s);
    document.getElementById('case-id').innerText = "%(id)s";
"""

class NoPanoramaException(Exception):
    pass

class StreetviewScreenshotClient():
    def __init__(self, window_size="1200,800", show_browser=False):
        chrome_opts = chrome.options.Options()
        if not show_browser: 
            chrome_opts.add_argument('--headless')
        chrome_opts.add_argument(f"window-size={window_size}")
        chrome_opts.add_argument("--log-level=3")
        chrome_svc = chrome.service.Service(log_output=os.devnull)
        self.driver = chrome.webdriver.WebDriver(service = chrome_svc, options=chrome_opts)
        self.wait = WebDriverWait(self.driver, 10)
    
    def take_screenshot(self):
        self.driver.find_element(By.ID, 'btn-screenshot').click()
        self.wait.until(EC.alert_is_present())
        self.driver.switch_to.alert.accept()
        time.sleep(.3)

    def move(self, direction, num_times=1):
        """
        The move script will try to click on the appropriate link
        """
        if direction == 'left':
            move_script = JS_MOVE_LEFT
        elif direction == 'right':
            move_script = JS_MOVE_RIGHT
        else:
            raise Exception('Left or Right only')
        # Move multiple times
        for _ in range(num_times):
            self.driver.execute_script(move_script)
            time.sleep(.5)

    def reset_intial_position(self):
        self.driver.execute_script(JS_RESET_INITIAL_POSITION)
        time.sleep(1.2)

    def reset_camera_to_coordinates(self, pitch=0):
        # Readjust the heading towards the building of interest
        self.driver.execute_script(JS_RESET_CAMERA % {'pitch': pitch})
        time.sleep(.5)

    def adjust_heading(self, deg, pitch=0):
        # Adjust the heading by the given amount of degrees and pitch
        # positive values turn the camera right, negative values left
        self.driver.execute_script(JS_ADJUST_HEADING % {'deg': deg, 'pitch': pitch})
        time.sleep(.5)

    def change_zoom(self, zoom):
        self.driver.execute_script(JS_CHANGE_ZOOM.format(zoom=zoom))
        time.sleep(.1)

    def set_date(self, pano, date):
        # print(pano, date)
        self.driver.execute_script(JS_CHANGE_DATE % {'pano': pano, 'date': date})
        time.sleep(1)

    def change_location(self, id, lat, lng):
        self.driver.execute_script(JS_CHANGE_LOCATION % {'id': id, 'lat': lat, 'lng': lng})
        time.sleep(1)

    def screenshot(self, cases, worker_id=0, additional_pano_selector=None):
        """
        Will try taking 7 images per date.
        additional_pano_selector is a function taking list of all available panos and a set 
        of the selected panos as arguments and returning additional panoramas to scrape.
        If none, it defaults to choosing the two earliest available panos.
        """
        if additional_pano_selector is None:
            # Default to taking 2 other available panos
            additional_pano_selector = lambda panos, _: panos[:2]
        
        driver = self.driver
        wait = self.wait

        total_cases = len(cases)

        needs_initialization = True
        for i, (id, lat, lng) in enumerate(cases):

            t0 = time.time()
            # Initialize the streetview for the first location
            if needs_initialization:
                # Initialize the streetview container at the initial coordinates
                try:
                    driver.get(f"http://127.0.0.1:5000/?id={id}&lat={lat}&lng={lng}")
                    # This is a proxy to know when the streetview is visible
                    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'gm-iv-address-link')))
                    time.sleep(.5)
                    needs_initialization = False

                except WebDriverException as e:
                    if 'ERR_CONNECTION_REFUSED' in e.msg:
                        print(f'ERROR - Could not connect to the server. Ensure it is running!')
                        return
                    traceback.print_exc()
                    continue

                # We throw an error alert if we can't load the streetview
                # AttributeError is also thrown sometimes when selenium can't find
                # an element matching '.gm-iv-address-link'
                except (UnexpectedAlertPresentException, AttributeError):
                    print(f'Worker {worker_id} - {id} ERROR ({i} / {total_cases})')
                    continue
            else:
                # Random sleep between location changes
                time.sleep(randrange(1, 2))
                self.change_location(id, lat, lng)

            try:
                # Get the initial pano id and date from the webpage
                current_pano = driver.find_element(By.ID, 'initial-pano').text
                current_date = driver.find_element(By.ID, 'current-date').text
                additional_panos = []
                panos_picked = set([current_pano])
                
                if other_panos_text := driver.find_element(By.ID, 'other-panos').text:
                    other_panos = json.loads(other_panos_text)
                    additional_panos = additional_pano_selector(other_panos, panos_picked)
                    
                all_dates = [{'pano': current_pano, 'date': current_date}] + additional_panos

                # Take all screenshots at this location
                for j, to_parse in enumerate(all_dates):
                    pano, date = to_parse.values()
                    if j > 0:
                        self.set_date(pano, date)
                    self.take_screenshot()
                    # Turn the camera right and left a bit
                    self.adjust_heading(60)
                    self.take_screenshot()
                    self.adjust_heading(-120)
                    self.take_screenshot()
                    self.reset_camera_to_coordinates()

                    self.move('right', num_times=1)
                    self.reset_camera_to_coordinates()
                    self.take_screenshot()

                    self.move('right', num_times=1)
                    self.reset_camera_to_coordinates()
                    self.take_screenshot()

                    self.reset_intial_position()

                    self.move('left', num_times=1)
                    self.reset_camera_to_coordinates()
                    self.take_screenshot()

                    self.move('left', num_times=1)
                    self.reset_camera_to_coordinates()
                    self.take_screenshot()

                print(f'Worker {worker_id} scraped {id} in {round(time.time() - t0,2)}s ({i} / {total_cases})')

            except KeyboardInterrupt:
                raise KeyboardInterrupt()
            # Thrown if a panorama can't be found within 100m of coordinates
            except UnexpectedAlertPresentException:
                print(f'Worker {worker_id} - {id} ERROR ({i} / {total_cases})')
                continue
            # Thrown when e.g. we can't find any links to move
            except JavascriptException:
                print(f'Worker {worker_id} - {id} ERROR ({i} / {total_cases})')
                continue
            except:
                print(traceback.format_exc())
                continue

    def __del__(self):
        try:
            self.driver.close()
        except:
            return


def select_one_winter_month(other_dates: list, panos_picked: set):
    """ 
    Get one winter month panorama if available,
    else the most recent other time period.
    """
    additional_panos = []
    # Reverse the list as dates are given from earliest
    # but we're more interested in recent panoramas
    for date in reversed(other_dates):
        month = date['date'].split(' ')[0]
        if month in ['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']:
            # Avoid duplicate panos
            if date['pano'] in panos_picked:
                continue
            additional_panos.append(date)
            panos_picked.add(date['pano'])
            return additional_panos
    
    # Fall back to taking another recent time period in case
    # there were no winter months
    for date in reversed(other_dates):
        # Avoid duplicate panos
        if date['pano'] in panos_picked:
            continue
        additional_panos.append(date)
        panos_picked.add(date['pano'])
        break

    return additional_panos
    

def screenshot_worker(split):
    cases, show_browser, worker_id = split
    client = StreetviewScreenshotClient(show_browser=show_browser)
    try:
        client.screenshot(cases, worker_id=worker_id, additional_pano_selector=select_one_winter_month)
    except KeyboardInterrupt:
        return
    except:
        print(traceback.format_exc())
        return


def split_cases_between_workers(cases, num_workers=1):
    splits = []
    cases_per_worker = math.ceil(len(cases) / num_workers)

    for i in range(num_workers):
        splits.append(cases[i * cases_per_worker : (i+1) * cases_per_worker])

    return splits


def launch_jobs(cases, num_workers: int, show_browser=False):
    # Split the cases between workers
    splits = split_cases_between_workers(cases, num_workers)
    # Add extra data the workers will need
    splits = [[s, show_browser, i] for i, s in enumerate(splits)]
    try:
        with Pool(processes=num_workers) as pool:
            # pool.map(get_screenshots_worker, splits)
            pool.map(screenshot_worker, splits)
    except KeyboardInterrupt:
        print('Interrupt received')
        exit()


def get_cases():
    # This would normally come from a database of some kind
    # We filter out the cases that were already scraped
    return [c for c in EXAMPLE_CASES if c not in set(list(Path(ENV['OUTPUT_DIR']).iterdir()))]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--num-workers', type=int, default=1, help="Number of parallel workers to launch")
    parser.add_argument('-s', '--image-size', type=str, default="1200,800", help="Width,height dimensions of images scraped")
    parser.add_argument('-b', '--show-browser', action='store_true', help="Show the browser windows.")
    args = parser.parse_args()

    launch_jobs(get_cases(), args.num_workers, args.show_browser)

