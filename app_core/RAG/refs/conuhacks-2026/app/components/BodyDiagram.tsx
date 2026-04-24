'use client';

import { useState } from 'react';

interface BodyDiagramProps {
  onBodyPartSelect: (bodyPart: string) => void;
  selectedParts: string[];
}

const bodyParts = {
  head: { label: 'Head', cx: 200, cy: 60, r: 35 },
  neck: { label: 'Neck', x: 175, y: 95, width: 50, height: 30 },
  leftShoulder: { label: 'Left Shoulder', cx: 140, cy: 135, r: 25 },
  rightShoulder: { label: 'Right Shoulder', cx: 260, cy: 135, r: 25 },
  chest: { label: 'Chest', x: 160, y: 125, width: 80, height: 70 },
  leftArm: { label: 'Left Arm', x: 110, y: 135, width: 30, height: 100 },
  rightArm: { label: 'Right Arm', x: 260, y: 135, width: 30, height: 100 },
  leftElbow: { label: 'Left Elbow', cx: 125, cy: 235, r: 18 },
  rightElbow: { label: 'Right Elbow', cx: 275, cy: 235, r: 18 },
  leftForearm: { label: 'Left Forearm', x: 110, y: 250, width: 30, height: 80 },
  rightForearm: { label: 'Right Forearm', x: 260, y: 250, width: 30, height: 80 },
  leftHand: { label: 'Left Hand', cx: 125, cy: 340, r: 20 },
  rightHand: { label: 'Right Hand', cx: 275, cy: 340, r: 20 },
  abdomen: { label: 'Abdomen', x: 160, y: 195, width: 80, height: 60 },
  leftHip: { label: 'Left Hip', cx: 170, cy: 275, r: 22 },
  rightHip: { label: 'Right Hip', cx: 230, cy: 275, r: 22 },
  leftThigh: { label: 'Left Thigh', x: 155, y: 290, width: 35, height: 90 },
  rightThigh: { label: 'Right Thigh', x: 210, y: 290, width: 35, height: 90 },
  leftKnee: { label: 'Left Knee', cx: 172, cy: 385, r: 20 },
  rightKnee: { label: 'Right Knee', cx: 228, cy: 385, r: 20 },
  leftLeg: { label: 'Left Shin', x: 157, y: 400, width: 30, height: 90 },
  rightLeg: { label: 'Right Shin', x: 213, y: 400, width: 30, height: 90 },
  leftFoot: { label: 'Left Foot', x: 152, y: 490, width: 40, height: 30 },
  rightFoot: { label: 'Right Foot', x: 208, y: 490, width: 40, height: 30 },
};

export default function BodyDiagram({ onBodyPartSelect, selectedParts }: BodyDiagramProps) {
  const [hoveredPart, setHoveredPart] = useState<string | null>(null);

  const handleBodyPartClick = (partKey: string, partLabel: string) => {
    onBodyPartSelect(partLabel);
  };

  const isSelected = (partKey: string) => {
    return selectedParts.includes(bodyParts[partKey as keyof typeof bodyParts].label);
  };

  const getColor = (partKey: string) => {
    if (isSelected(partKey)) return '#ef4444'; // red for selected
    if (hoveredPart === partKey) return '#60a5fa'; // blue for hover
    return '#e5e7eb'; // gray default
  };

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox="0 0 400 550"
        className="w-full max-w-md"
        style={{ maxHeight: '550px' }}
      >
        {/* Head */}
        <circle
          cx={bodyParts.head.cx}
          cy={bodyParts.head.cy}
          r={bodyParts.head.r}
          fill={getColor('head')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('head')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('head', bodyParts.head.label)}
        />

        {/* Neck */}
        <rect
          x={bodyParts.neck.x}
          y={bodyParts.neck.y}
          width={bodyParts.neck.width}
          height={bodyParts.neck.height}
          fill={getColor('neck')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('neck')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('neck', bodyParts.neck.label)}
        />

        {/* Shoulders */}
        <circle
          cx={bodyParts.leftShoulder.cx}
          cy={bodyParts.leftShoulder.cy}
          r={bodyParts.leftShoulder.r}
          fill={getColor('leftShoulder')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftShoulder')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftShoulder', bodyParts.leftShoulder.label)}
        />
        <circle
          cx={bodyParts.rightShoulder.cx}
          cy={bodyParts.rightShoulder.cy}
          r={bodyParts.rightShoulder.r}
          fill={getColor('rightShoulder')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightShoulder')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightShoulder', bodyParts.rightShoulder.label)}
        />

        {/* Chest */}
        <rect
          x={bodyParts.chest.x}
          y={bodyParts.chest.y}
          width={bodyParts.chest.width}
          height={bodyParts.chest.height}
          rx="10"
          fill={getColor('chest')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('chest')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('chest', bodyParts.chest.label)}
        />

        {/* Arms */}
        <rect
          x={bodyParts.leftArm.x}
          y={bodyParts.leftArm.y}
          width={bodyParts.leftArm.width}
          height={bodyParts.leftArm.height}
          rx="15"
          fill={getColor('leftArm')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftArm')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftArm', bodyParts.leftArm.label)}
        />
        <rect
          x={bodyParts.rightArm.x}
          y={bodyParts.rightArm.y}
          width={bodyParts.rightArm.width}
          height={bodyParts.rightArm.height}
          rx="15"
          fill={getColor('rightArm')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightArm')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightArm', bodyParts.rightArm.label)}
        />

        {/* Elbows */}
        <circle
          cx={bodyParts.leftElbow.cx}
          cy={bodyParts.leftElbow.cy}
          r={bodyParts.leftElbow.r}
          fill={getColor('leftElbow')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftElbow')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftElbow', bodyParts.leftElbow.label)}
        />
        <circle
          cx={bodyParts.rightElbow.cx}
          cy={bodyParts.rightElbow.cy}
          r={bodyParts.rightElbow.r}
          fill={getColor('rightElbow')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightElbow')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightElbow', bodyParts.rightElbow.label)}
        />

        {/* Forearms */}
        <rect
          x={bodyParts.leftForearm.x}
          y={bodyParts.leftForearm.y}
          width={bodyParts.leftForearm.width}
          height={bodyParts.leftForearm.height}
          rx="15"
          fill={getColor('leftForearm')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftForearm')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftForearm', bodyParts.leftForearm.label)}
        />
        <rect
          x={bodyParts.rightForearm.x}
          y={bodyParts.rightForearm.y}
          width={bodyParts.rightForearm.width}
          height={bodyParts.rightForearm.height}
          rx="15"
          fill={getColor('rightForearm')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightForearm')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightForearm', bodyParts.rightForearm.label)}
        />

        {/* Hands */}
        <circle
          cx={bodyParts.leftHand.cx}
          cy={bodyParts.leftHand.cy}
          r={bodyParts.leftHand.r}
          fill={getColor('leftHand')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftHand')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftHand', bodyParts.leftHand.label)}
        />
        <circle
          cx={bodyParts.rightHand.cx}
          cy={bodyParts.rightHand.cy}
          r={bodyParts.rightHand.r}
          fill={getColor('rightHand')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightHand')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightHand', bodyParts.rightHand.label)}
        />

        {/* Abdomen */}
        <rect
          x={bodyParts.abdomen.x}
          y={bodyParts.abdomen.y}
          width={bodyParts.abdomen.width}
          height={bodyParts.abdomen.height}
          rx="10"
          fill={getColor('abdomen')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('abdomen')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('abdomen', bodyParts.abdomen.label)}
        />

        {/* Hips */}
        <circle
          cx={bodyParts.leftHip.cx}
          cy={bodyParts.leftHip.cy}
          r={bodyParts.leftHip.r}
          fill={getColor('leftHip')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftHip')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftHip', bodyParts.leftHip.label)}
        />
        <circle
          cx={bodyParts.rightHip.cx}
          cy={bodyParts.rightHip.cy}
          r={bodyParts.rightHip.r}
          fill={getColor('rightHip')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightHip')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightHip', bodyParts.rightHip.label)}
        />

        {/* Thighs */}
        <rect
          x={bodyParts.leftThigh.x}
          y={bodyParts.leftThigh.y}
          width={bodyParts.leftThigh.width}
          height={bodyParts.leftThigh.height}
          rx="17"
          fill={getColor('leftThigh')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftThigh')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftThigh', bodyParts.leftThigh.label)}
        />
        <rect
          x={bodyParts.rightThigh.x}
          y={bodyParts.rightThigh.y}
          width={bodyParts.rightThigh.width}
          height={bodyParts.rightThigh.height}
          rx="17"
          fill={getColor('rightThigh')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightThigh')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightThigh', bodyParts.rightThigh.label)}
        />

        {/* Knees */}
        <circle
          cx={bodyParts.leftKnee.cx}
          cy={bodyParts.leftKnee.cy}
          r={bodyParts.leftKnee.r}
          fill={getColor('leftKnee')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftKnee')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftKnee', bodyParts.leftKnee.label)}
        />
        <circle
          cx={bodyParts.rightKnee.cx}
          cy={bodyParts.rightKnee.cy}
          r={bodyParts.rightKnee.r}
          fill={getColor('rightKnee')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightKnee')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightKnee', bodyParts.rightKnee.label)}
        />

        {/* Lower Legs */}
        <rect
          x={bodyParts.leftLeg.x}
          y={bodyParts.leftLeg.y}
          width={bodyParts.leftLeg.width}
          height={bodyParts.leftLeg.height}
          rx="15"
          fill={getColor('leftLeg')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftLeg')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftLeg', bodyParts.leftLeg.label)}
        />
        <rect
          x={bodyParts.rightLeg.x}
          y={bodyParts.rightLeg.y}
          width={bodyParts.rightLeg.width}
          height={bodyParts.rightLeg.height}
          rx="15"
          fill={getColor('rightLeg')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightLeg')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightLeg', bodyParts.rightLeg.label)}
        />

        {/* Feet */}
        <rect
          x={bodyParts.leftFoot.x}
          y={bodyParts.leftFoot.y}
          width={bodyParts.leftFoot.width}
          height={bodyParts.leftFoot.height}
          rx="8"
          fill={getColor('leftFoot')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('leftFoot')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('leftFoot', bodyParts.leftFoot.label)}
        />
        <rect
          x={bodyParts.rightFoot.x}
          y={bodyParts.rightFoot.y}
          width={bodyParts.rightFoot.width}
          height={bodyParts.rightFoot.height}
          rx="8"
          fill={getColor('rightFoot')}
          stroke="#374151"
          strokeWidth="2"
          className="cursor-pointer transition-colors"
          onMouseEnter={() => setHoveredPart('rightFoot')}
          onMouseLeave={() => setHoveredPart(null)}
          onClick={() => handleBodyPartClick('rightFoot', bodyParts.rightFoot.label)}
        />
      </svg>

      {/* Legend */}
      <div className="mt-4 text-center">
        <p className="text-sm text-gray-600 mb-2">
          {hoveredPart ? (
            <span className="font-semibold text-blue-600">
              {bodyParts[hoveredPart as keyof typeof bodyParts].label}
            </span>
          ) : (
            'Click on the body part that hurts'
          )}
        </p>
        <div className="flex items-center justify-center gap-4 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <div className="w-4 h-4 bg-gray-200 border border-gray-400 rounded"></div>
            <span>Unselected</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-4 bg-red-500 border border-gray-400 rounded"></div>
            <span>Selected</span>
          </div>
        </div>
      </div>
    </div>
  );
}

