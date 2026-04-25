import React, { useEffect, useLayoutEffect, useRef, useId, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MapView.css';

// Custom icon for markers
const createMarkerIcon = (color = '#0b3d91') => {
  return L.divIcon({
    html: `<div style="
      background-color: ${color};
      color: white;
      border-radius: 50%;
      width: 28px;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 14px;
      border: 3px solid white;
      box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    ">📍</div>`,
    className: 'map-view-marker',
    iconSize: [28, 28],
    iconAnchor: [14, 28],
  });
};

const normalizeWaypoints = (raw) => {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((w) => {
      const lat = w.lat != null ? Number(w.lat) : w.latitude != null ? Number(w.latitude) : NaN;
      const lng = w.lng != null ? Number(w.lng) : w.longitude != null ? Number(w.longitude) : NaN;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
      return { ...w, lat, lng, name: w.name || w.title || w.place_name || 'Stop' };
    })
    .filter(Boolean);
};

/**
 * MapView Component - Interactive map showing waypoints
 * @param {Array} waypoints - Array of {id, name, lat, lng} (or latitude/longitude)
 * @param {String} height - CSS height value (default: '400px')
 * @param {Number} [defaultZoom] - Initial zoom when map mounts; if omitted, 12 with waypoints, 5 without
 */
export default function MapView({ waypoints: waypointsProp = [], height = '400px', defaultZoom = null }) {
  const waypoints = useMemo(() => normalizeWaypoints(waypointsProp), [waypointsProp]);
  const mapRef = useRef(null);
  const mapStateRef = useRef(null);
  const markersRef = useRef([]);
  const initialDefaultZoom = useRef(defaultZoom);
  const reactId = useId();
  const containerId = `leaflet-map-${reactId.replace(/:/g, '')}`;

  // Create map in layout effect so the container ref exists before the markers effect runs
  useLayoutEffect(() => {
    if (typeof window === 'undefined' || !mapRef.current) return;

    const el = mapRef.current;
    const startZoom = initialDefaultZoom.current != null ? initialDefaultZoom.current : 5;
    const mapInstance = L.map(el).setView([24.5, 67.0], startZoom);
    mapStateRef.current = mapInstance;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
      tileSize: 256,
    }).addTo(mapInstance);

    requestAnimationFrame(() => {
      mapInstance.invalidateSize();
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      mapInstance.remove();
      mapStateRef.current = null;
    };
  }, []);

  // Markers and bounds (depends on data from parent)
  useEffect(() => {
    const map = mapStateRef.current;
    if (!map) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (waypoints.length === 0) {
      return;
    }

    const newMarkers = waypoints.map((wp, idx) => {
      const color = idx === 0 ? '#10b981' : idx === waypoints.length - 1 ? '#dc2626' : '#0b3d91';
      const latStr = Number(wp.lat).toFixed(4);
      const lngStr = Number(wp.lng).toFixed(4);
      const safeName = String(wp.name).replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const addressHtml =
        wp.address != null
          ? `<p style="margin: 0 0 8px; color: #475569; font-size: 0.9rem;">${String(wp.address)
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')}</p>`
          : '';

      const marker = L.marker([wp.lat, wp.lng], {
        icon: createMarkerIcon(color),
        title: wp.name,
      })
        .bindPopup(`
          <div style="font-family: sans-serif; width: 200px;">
            <h3 style="margin: 0 0 6px; color: #0b2140; font-size: 1rem;">${safeName}</h3>
            ${addressHtml}
            <p style="margin: 0; color: #64748b; font-size: 0.85rem;">
              <strong>Lat:</strong> ${latStr}<br/>
              <strong>Lng:</strong> ${lngStr}
            </p>
          </div>
        `)
        .addTo(map);

      return marker;
    });

    markersRef.current = newMarkers;

    if (newMarkers.length > 0) {
      const group = new L.featureGroup(newMarkers);
      map.fitBounds(group.getBounds(), { padding: [20, 20], maxZoom: 18 });
    }

    requestAnimationFrame(() => {
      map.invalidateSize();
    });
  }, [waypoints]);

  return (
    <div
      id={containerId}
      ref={mapRef}
      className="map-view-leaflet-root"
      style={{
        width: '100%',
        height: height,
        borderRadius: '14px',
        border: '2px solid #e2e8f0',
        boxShadow: '0 4px 16px rgba(2,6,23,0.06)',
        overflow: 'hidden',
        zIndex: 1,
      }}
    />
  );
}
