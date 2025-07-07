import React, { useEffect, useState } from 'react';
import * as d3 from 'd3';

export default function FraudHeatmap() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch('/api/fraud-stats')
      .then(res => res.json())
      .then(data => {
        const heatmapData = d3.rollup(
          data, 
          v => d3.mean(v, d => d.risk_score), 
          d => d.geo_country, 
          d => d.hour_of_day
        );
        setData(heatmapData);
      });
  }, []);

  return (
    <div className="heatmap">
      {Array.from(data).map(([country, hours]) => (
        <div key={country} className="country-row">
          <div className="country-label">{country}</div>
          {Array.from(hours).map(([hour, score]) => (
            <div 
              key={hour} 
              className="hour-cell"
              style={{ opacity: score }}
              title={`${country} @ ${hour}:00 - Risk: ${score.toFixed(2)}`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

