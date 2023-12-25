// Retrieve data passed to the script from the template
const mapsData = document.currentScript.dataset;

(async function initMap() {
  const { StreetViewService } = await google.maps.importLibrary("streetView");
  const svService = new StreetViewService();

  let coordinates = { 
    lat: parseFloat(mapsData.lat),
    lng: parseFloat(mapsData.lng),
  };
  window.coordinates = coordinates; // Used to readjust the heading

  let panoRequest = {
    location: coordinates,
    preference: google.maps.StreetViewPreference.NEAREST,
    radius: 10,
    source: google.maps.StreetViewSource.OUTDOOR
  };
  findPanorama(svService, panoRequest);
})();


async function changeMapPosition(lat, lng) {
  const { StreetViewService } = await google.maps.importLibrary("streetView");
  const svService = new StreetViewService();

  let coordinates = { 
    lat: lat,
    lng: lng,
  };
  window.coordinates = coordinates; // Used to readjust the heading

  let panoRequest = {
    location: coordinates,
    preference: google.maps.StreetViewPreference.NEAREST,
    radius: 10,
    source: google.maps.StreetViewSource.OUTDOOR
  };
  await changeLocations(svService, panoRequest);
}

/* 
* Get the date key.
* Assumptions:
* - The panorama key is 'pano'
* - There are only 2 keys in each object
*/
function getPanoDateKey(panoArray) {
  return Object.keys(panoArray[0]).filter((e) => {return e !== 'pano'})[0];
}

function getPanoDate(panoDate) {
  const dateSplit = panoDate.split('-');
  const date = new Date(dateSplit[0], parseInt(dateSplit[1]) - 1, 1);
  return date.toLocaleDateString('en-US', { year: "numeric", month: "short"});
}

function getOtherPanosWithDates(otherPanos) {
  const key = getPanoDateKey(otherPanos);
  return otherPanos.map(el => (
    {'pano': el['pano'], 'date': el[key].toLocaleDateString('en-US', { year:"numeric", month:"short"})}
  ))
}

async function findPanorama(svService, panoRequest) {
  const { spherical } = await google.maps.importLibrary("geometry");
  const { StreetViewStatus, StreetViewPanorama } = await google.maps.importLibrary("streetView");
  const { Marker } = await google.maps.importLibrary("marker");
  const coordinates = panoRequest.location;

  // Send a request to the panorama service
  svService.getPanorama(panoRequest, (panoData, status) => {
    if (status === StreetViewStatus.OK) 
    {
      console.debug(`Status ${status}: panorama found.`);
      console.debug(JSON.stringify(panoData, null, 2));
      
      const panoId = panoData.location.pano;
      const panoDate = getPanoDate(panoData.imageDate);
      const otherPanos = getOtherPanosWithDates(panoData.time);
      const heading = spherical.computeHeading(panoData.location.latLng, coordinates);
      // Zoom in if the target location is further away
      const dist = distBetween(coordinates, panoData.location.latLng);
      const zoom = getZoomLevel(dist);
      // Instanciate the street view - this incurs a 0.014 USD charge
      const sv = new StreetViewPanorama(
        document.getElementById('streetview'),
        {
          position: coordinates,
          center: coordinates,
          zoom: zoom,
          pov: {
            pitch: 0,
            heading: heading,
          },
        }
      );
      sv.setPano(panoId);
      // For convenience when opening the web page in a browser
      // gets removed from the screenshots
      const sv_marker = new Marker({
        position: coordinates,
        map: sv,
      });
      
      // Store these for easy access later
      window.sv = sv;
      window.sv_marker = sv_marker;
      window.computeHeading = spherical.computeHeading;
      document.getElementById('initial-pano').innerText = panoId;
      document.getElementById('current-date').innerText = panoDate
      document.getElementById('other-panos').innerText = JSON.stringify(otherPanos);
    }
    else {
      const radius = panoRequest.radius
      if (radius >= 100) {
        console.log(`Status ${status}: Could not find panorama within ${radius}m! Giving up.`);
        alert('ERROR');
      }
      else {
        // Retry with an increased search radius
        panoRequest.radius += 25;
        console.log(`Status ${status}: could not find panorama within ${radius}m, trying ${panoRequest.radius}m.`);
        return findPanorama(svService, panoRequest, coordinates);
      }
    }
  });
}

function getZoomLevel(dist) {
  return dist < 50 ? 0
    : dist < 75 ? 1
    : dist < 100 ? 1.5
    : 2;
}

async function changeLocations(svService, panoRequest) {
  const { spherical } = await google.maps.importLibrary("geometry");
  const { StreetViewStatus } = await google.maps.importLibrary("streetView");
  const coordinates = panoRequest.location;

  // Send a request to the panorama service
  svService.getPanorama(panoRequest, (panoData, status) => {
    if (status === StreetViewStatus.OK) 
    {
      console.debug(`Status ${status}: panorama found.`);
      console.debug(JSON.stringify(panoData, null, 2));
      
      const panoId = panoData.location.pano;
      const panoDate = getPanoDate(panoData.imageDate);
      const otherPanos = getOtherPanosWithDates(panoData.time);
      const heading = spherical.computeHeading(panoData.location.latLng, coordinates);
      
      // Adjust the zoom level based on distance to the location
      const dist = distBetween(coordinates, panoData.location.latLng);
      const zoom = getZoomLevel(dist);
      
      // Update the streetview
      window.sv.setPano(panoId);
      window.sv.setPov({heading: heading, pitch: 0});
      window.sv.setZoom(zoom);
      window.sv_marker.setPosition(coordinates);
      
      // Store these in the document for the client to access
      document.getElementById('initial-pano').innerText = panoId;
      document.getElementById('current-date').innerText = panoDate
      document.getElementById('other-panos').innerText = JSON.stringify(otherPanos);
    }
    else {
      const radius = panoRequest.radius
      if (radius >= 100) {
        console.log(`Status ${status}: Could not find panorama within ${radius}m! Giving up.`);
        alert('ERROR');
      }
      else {
        panoRequest.radius += 25;
        console.log(`Status ${status}: could not find panorama within ${radius}m, trying ${panoRequest.radius}m.`);
        return changeLocations(svService, panoRequest);
      }
    }
  });
}


// Functions to control the streetview
function moveRight() {
  // The query selector fot the links are likely only valid for v3.53
  // of the JS API and may have to be update in the future. 
  const links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
  var index = 0;
  if (links.length === 2 || links.length === 3)
      index = 0;
  else if (links.length === 4)
      index = 1;
  links[index].dispatchEvent(new Event('click', {bubbles: true}));
}

function moveLeft() {
  const links = document.querySelector('div.gmnoprint.SLHIdE-sv-links-control').firstChild.querySelectorAll('[role="button"]');
  var index = 0;
  if (links.length === 2)
      index = 1;
  else if (links.length === 3 || links.length === 4)
      index = 2;
  links[index].dispatchEvent(new Event('click', {bubbles: true}));
  links[index].dispatchEvent(new Event('click', {bubbles: true}));
}

function adjustHeading(deg=70, pitch=0) {
  window.sv.setPov({
    heading: window.sv.pov.heading + deg, 
    pitch: pitch
});
}

function resetCamera(pitch=0) {
  window.sv.setPov({
    heading: window.computeHeading(window.sv.getPosition().toJSON(), window.coordinates), 
    pitch: pitch
});
}

// Adapted from https://cloud.google.com/blog/products/maps-platform/how-calculate-distances-map-maps-javascript-api
function distBetween(coords, latLng) {
  var R = 6_378_137; // Radius of the Earth in meters
  var rlat1 = coords.lat * (Math.PI/180); // Convert degrees to radians
  var rlat2 = latLng.lat() * (Math.PI/180); // Convert degrees to radians
  var difflat = rlat2-rlat1; // Radian difference (latitudes)
  var difflon = (coords.lng - latLng.lng()) * (Math.PI/180); // Radian difference (longitudes)
  var d = 2 * R * Math.asin(Math.sqrt(Math.sin(difflat/2)*Math.sin(difflat/2)+Math.cos(rlat1)*Math.cos(rlat2)*Math.sin(difflon/2)*Math.sin(difflon/2)));
  return d;
}

function distTo(coords) {
  return distBetween(coords, window.sv.position);
}